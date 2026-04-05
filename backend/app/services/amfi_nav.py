"""AMFI NAVAll.txt: ISIN → latest published NAV and date (cached)."""

from __future__ import annotations

import logging
import re
import time
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NAV_ALL_URL = "https://www.amfiindia.com/spages/NAVAll.txt"
_CACHE_TTL_SEC = 3600
_ISIN_RE = re.compile(r"^IN[A-Z0-9]{10}$")

_cache: dict[str, Any] = {"ts": 0.0, "by_isin": {}}


def _parse_nav_date(s: str) -> datetime | None:
    s = (s or "").strip()
    for fmt in ("%d-%b-%Y", "%d-%B-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _valid_isin(token: str) -> str | None:
    t = token.strip().upper()
    if _ISIN_RE.match(t):
        return t
    return None


def _fetch_and_parse() -> dict[str, dict[str, Any]]:
    """Parse NAVAll.txt into isin -> {nav, nav_date, scheme_code, scheme_name}."""
    by_isin: dict[str, dict[str, Any]] = {}
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            r = client.get(NAV_ALL_URL)
            r.raise_for_status()
            text = r.text
    except Exception as e:
        logger.warning("AMFI NAVAll fetch failed: %s", e)
        return by_isin

    for line in text.splitlines():
        line = line.strip()
        if ";" not in line or line.startswith("Open Ended") or line.startswith("Close Ended"):
            continue
        parts = [p.strip() for p in line.split(";")]
        # Current AMFI format: code;ISIN;ISIN/reinv;scheme name;NAV;dd-Mon-yyyy
        if len(parts) >= 6 and parts[0].isdigit():
            code, isin_a, isin_b, name = parts[0], parts[1], parts[2], parts[3]
            try:
                nav = float(parts[4].replace(",", ""))
            except ValueError:
                continue
            date_raw = parts[5]
            dt = _parse_nav_date(date_raw)
            if dt is None:
                continue
            date_str = dt.strftime("%Y-%m-%d")
            for raw_isin in (isin_a, isin_b):
                if raw_isin in ("", "-", "NA"):
                    continue
                isin = _valid_isin(raw_isin)
                if not isin:
                    continue
                prev = by_isin.get(isin)
                if prev is None or date_str >= prev.get("nav_date", ""):
                    by_isin[isin] = {
                        "nav": nav,
                        "nav_date": date_str,
                        "scheme_code": code,
                        "scheme_name": name,
                    }
            continue
        # Legacy 8-column rows (code;name;isin;isin;nav;rep;sale;date)
        if len(parts) >= 8 and parts[0].isdigit():
            code, name, isin_a, isin_b = parts[0], parts[1], parts[2], parts[3]
            try:
                nav = float(parts[4].replace(",", ""))
            except ValueError:
                continue
            date_raw = parts[7]
            dt = _parse_nav_date(date_raw)
            if dt is None:
                continue
            date_str = dt.strftime("%Y-%m-%d")
            for raw_isin in (isin_a, isin_b):
                if raw_isin in ("", "-", "NA"):
                    continue
                isin = _valid_isin(raw_isin)
                if not isin:
                    continue
                prev = by_isin.get(isin)
                if prev is None or date_str >= prev.get("nav_date", ""):
                    by_isin[isin] = {
                        "nav": nav,
                        "nav_date": date_str,
                        "scheme_code": code,
                        "scheme_name": name,
                    }
    logger.info("AMFI NAV cache: %d ISINs parsed", len(by_isin))
    return by_isin


def get_isin_nav_map() -> dict[str, dict[str, Any]]:
    now = time.time()
    if now - float(_cache["ts"]) < _CACHE_TTL_SEC and _cache["by_isin"]:
        return _cache["by_isin"]  # type: ignore[return-value]
    by_isin = _fetch_and_parse()
    _cache["ts"] = now
    _cache["by_isin"] = by_isin
    return by_isin


def fetch_mf_nav_by_isin(isin: str) -> tuple[float | None, str | None, bool]:
    """
    Latest published NAV for ISIN from AMFI NAVAll.
    Returns (nav, nav_date_iso, ok).
    """
    isin_u = (isin or "").strip().upper()
    if not _ISIN_RE.match(isin_u):
        return None, None, False
    m = get_isin_nav_map().get(isin_u)
    if not m:
        return None, None, False
    return float(m["nav"]), str(m.get("nav_date")), True


def lookup_isin_meta(isin: str) -> dict[str, Any] | None:
    isin_u = (isin or "").strip().upper()
    return get_isin_nav_map().get(isin_u)
