"""Fetch mutual fund scheme details and holdings from mfdata.in (free, no auth)."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_BASE = "https://mfdata.in/api/v1"
_TIMEOUT = 15.0

_scheme_cache: dict[str, dict[str, Any]] = {}
_scheme_cache_ts: dict[str, float] = {}
_CACHE_TTL = 3600


def _get_json(path: str) -> dict[str, Any] | None:
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as c:
            r = c.get(f"{_BASE}{path}")
            if r.status_code != 200:
                return None
            return r.json()
    except Exception as e:
        logger.warning("mfdata.in %s failed: %s", path, e)
        return None


def get_scheme_profile(scheme_code: str) -> dict[str, Any] | None:
    """Full scheme profile: NAV, returns, ratios, expense ratio, AUM, family_id."""
    now = time.time()
    ck = f"profile:{scheme_code}"
    if ck in _scheme_cache and now - _scheme_cache_ts.get(ck, 0) < _CACHE_TTL:
        return _scheme_cache[ck]
    data = _get_json(f"/schemes/{scheme_code}")
    if data and data.get("status") == "success":
        _scheme_cache[ck] = data.get("data", {})
        _scheme_cache_ts[ck] = now
        return _scheme_cache[ck]
    return None


def get_family_holdings(family_id: int | str) -> list[dict[str, Any]]:
    """Top stock-level portfolio holdings for a fund family."""
    now = time.time()
    ck = f"holdings:{family_id}"
    if ck in _scheme_cache and now - _scheme_cache_ts.get(ck, 0) < _CACHE_TTL:
        return _scheme_cache[ck].get("holdings", [])  # type: ignore[union-attr]
    data = _get_json(f"/families/{family_id}/holdings")
    if data and data.get("status") == "success":
        holdings = data.get("data", {}).get("holdings", [])
        _scheme_cache[ck] = {"holdings": holdings}
        _scheme_cache_ts[ck] = now
        return holdings
    return []


def search_scheme_by_name(name: str) -> dict[str, Any] | None:
    """Search mfdata.in by scheme name, return best direct-plan match profile."""
    if not name or len(name) < 4:
        return None
    query = name.split(" - ")[0].strip()[:60]
    data = _get_json(f"/search?q={query}&limit=5")
    if not data or data.get("status") != "success":
        return None
    results = data.get("data") or []
    for r in results:
        sn = (r.get("scheme_name") or "").lower()
        if "direct" in sn and ("growth" in sn or "plan" in sn):
            code = r.get("scheme_code")
            if code:
                return get_scheme_profile(str(code))
    if results:
        code = results[0].get("scheme_code")
        if code:
            return get_scheme_profile(str(code))
    return None


def search_and_enrich(name: str) -> dict[str, Any]:
    """Enrich by searching mfdata.in by fund name when amfi code doesn't work."""
    profile = search_scheme_by_name(name)
    if not profile:
        return {}
    result: dict[str, Any] = {
        "scheme_name": profile.get("scheme_name", ""),
        "category": profile.get("category", ""),
        "aum_cr": profile.get("aum_cr"),
        "expense_ratio": profile.get("expense_ratio"),
        "morningstar": profile.get("morningstar"),
    }
    returns = profile.get("returns")
    if isinstance(returns, dict):
        result["returns"] = {
            k: v.get("value") if isinstance(v, dict) else v
            for k, v in returns.items()
            if k in ("1m", "3m", "6m", "1y", "3y", "5y")
        }
    ratios = profile.get("ratios")
    if isinstance(ratios, dict):
        result["ratios"] = {
            k: ratios[k] for k in ("sharpe", "beta", "alpha", "pe", "std_dev") if k in ratios
        }
    family_id = profile.get("family_id")
    if family_id:
        holdings = get_family_holdings(family_id)
        result["top_holdings"] = [
            {"stock": h.get("stock_name", ""), "weight": h.get("weight_pct")}
            for h in holdings[:10]
        ]
    return result


def enrich_mf_for_advisor(amfi_code: str) -> dict[str, Any]:
    """Build a compact summary of a fund: returns, top holdings, ratios."""
    profile = get_scheme_profile(amfi_code)
    if not profile:
        return {}
    result: dict[str, Any] = {
        "scheme_name": profile.get("scheme_name", ""),
        "category": profile.get("category", ""),
        "aum_cr": profile.get("aum_cr"),
        "expense_ratio": profile.get("expense_ratio"),
        "morningstar": profile.get("morningstar"),
    }
    returns = profile.get("returns")
    if isinstance(returns, dict):
        result["returns"] = {
            k: v.get("value") if isinstance(v, dict) else v
            for k, v in returns.items()
            if k in ("1m", "3m", "6m", "1y", "3y", "5y")
        }
    ratios = profile.get("ratios")
    if isinstance(ratios, dict):
        result["ratios"] = {
            k: ratios[k] for k in ("sharpe", "beta", "alpha", "pe", "std_dev") if k in ratios
        }
    family_id = profile.get("family_id")
    if family_id:
        holdings = get_family_holdings(family_id)
        result["top_holdings"] = [
            {"stock": h.get("stock_name", ""), "weight": h.get("weight_pct")}
            for h in holdings[:10]
        ]
    return result
