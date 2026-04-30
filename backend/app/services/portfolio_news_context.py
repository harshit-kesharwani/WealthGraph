"""Build news search context from stocks + mutual funds, weighted by sector & MF category focus."""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from typing import Any

import yfinance as yf

from app.services.mfdata_service import enrich_mf_for_advisor, search_and_enrich
from app.services.valuation import _normalize_equity_ticker, value_portfolio

logger = logging.getLogger(__name__)

MAX_MF_LINES_TO_ENRICH = 10
MAX_HOLDING_NAMES_FOR_QUERY = 18
MAX_EQUITY_SECTOR_LOOKUPS = 10
_SECTOR_CACHE: dict[str, tuple[str | None, str | None, float]] = {}
_SECTOR_CACHE_TTL = 6 * 3600


def _clean_stock_name(name: str) -> str:
    n = (name or "").strip()
    if not n:
        return ""
    n = re.sub(r"\s+", " ", n)
    for suffix in (
        " Limited",
        " Ltd",
        " Ltd.",
        " Pvt Ltd",
        " Private Limited",
        " Corporation",
        " Corp",
        " Inc",
    ):
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
    return n[:80]


def _yf_sector_industry(ticker: str) -> tuple[str | None, str | None]:
    """Sector/industry from yfinance (cached)."""
    key = str(ticker).strip().upper()
    if not key:
        return None, None
    now = time.time()
    hit = _SECTOR_CACHE.get(key)
    if hit and now - hit[2] < _SECTOR_CACHE_TTL:
        return hit[0], hit[1]
    sector, industry = None, None
    try:
        sym = _normalize_equity_ticker(key)
        info = yf.Ticker(sym).info or {}
        sector = info.get("sector") or None
        industry = info.get("industry") or None
        if isinstance(sector, str):
            sector = sector.strip() or None
        if isinstance(industry, str):
            industry = industry.strip() or None
    except Exception as e:
        logger.debug("yfinance sector for %s: %s", key, e)
    _SECTOR_CACHE[key] = (sector, industry, now)
    return sector, industry


def _normalize_category_label(cat: str) -> str:
    c = (cat or "").strip()
    if not c:
        return "General / other"
    return c[:100]


def _pct(part: float, whole: float) -> float:
    if whole <= 0:
        return 0.0
    return round(100.0 * part / whole, 1)


def build_portfolio_news_context(
    portfolio: dict[str, Any],
    last_prices_fb: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Value-weighted sector (direct equity) + MF category mix, tickers, MF top holdings for news + UI.
    """
    fb = dict(last_prices_fb or {})
    v = value_portfolio(portfolio, fb)
    stocks = portfolio.get("stocks") or []
    mfs = portfolio.get("mutualFunds") or []
    equity_rows = list(v.get("equity") or [])
    mf_rows = list(v.get("mutualFunds") or [])

    tickers: list[str] = []
    seen_t = set()
    for s in stocks:
        t = str(s.get("ticker", "")).strip().upper()
        if t and t not in seen_t:
            seen_t.add(t)
            tickers.append(t)

    fund_labels: list[str] = []
    mf_holding_names: list[str] = []
    seen_names: set[str] = set()
    category_value: defaultdict[str, float] = defaultdict(float)

    for i, mf in enumerate(mfs):
        if i >= MAX_MF_LINES_TO_ENRICH:
            break
        code = str(mf.get("amfiCode") or "").strip()
        fund_name = str(mf.get("name") or "").strip()
        if fund_name and fund_name not in fund_labels:
            fund_labels.append(fund_name[:120])

        enriched: dict[str, Any] = {}
        try:
            if code:
                enriched = enrich_mf_for_advisor(code)
            if not enriched and fund_name and len(fund_name) > 4:
                enriched = search_and_enrich(fund_name)
        except Exception as e:
            logger.warning("MF enrich for news context failed: %s", e)
            enriched = {}

        cat = _normalize_category_label(str(enriched.get("category") or ""))
        mv = 0.0
        if i < len(mf_rows):
            mv = float(mf_rows[i].get("currentValue") or 0)
        if mv > 0:
            category_value[cat] += mv

        for h in enriched.get("top_holdings") or []:
            if not isinstance(h, dict):
                continue
            raw = str(h.get("stock") or "").strip()
            cleaned = _clean_stock_name(raw)
            if not cleaned or len(cleaned) < 2:
                continue
            key = cleaned.lower()
            if key in seen_names:
                continue
            seen_names.add(key)
            mf_holding_names.append(cleaned)
            if len(mf_holding_names) >= MAX_HOLDING_NAMES_FOR_QUERY:
                break
        if len(mf_holding_names) >= MAX_HOLDING_NAMES_FOR_QUERY:
            break

    sector_value: defaultdict[str, float] = defaultdict(float)
    sorted_eq = sorted(equity_rows, key=lambda r: float(r.get("currentValue") or 0), reverse=True)
    for row in sorted_eq[:MAX_EQUITY_SECTOR_LOOKUPS]:
        t = str(row.get("ticker", "")).strip().upper()
        val = float(row.get("currentValue") or 0)
        if not t or val <= 0:
            continue
        sec, _ind = _yf_sector_industry(t)
        label = sec or "Unclassified equity"
        sector_value[label] += val

    risk_assets = float(sum(float(r.get("currentValue") or 0) for r in equity_rows))
    risk_assets += float(sum(float(r.get("currentValue") or 0) for r in mf_rows))
    cash = float(v.get("cash") or 0)
    nw = float(v.get("netWorth") or 0)

    top_stock_sectors = sorted(
        (
            {"sector": s, "value": val, "pctOfRiskAssets": _pct(val, risk_assets)}
            for s, val in sector_value.items()
            if val > 0
        ),
        key=lambda x: x["value"],
        reverse=True,
    )[:8]

    top_mf_categories = sorted(
        (
            {"category": c, "value": val, "pctOfRiskAssets": _pct(val, risk_assets)}
            for c, val in category_value.items()
            if val > 0
        ),
        key=lambda x: x["value"],
        reverse=True,
    )[:8]

    theme_search_phrases = _build_theme_search_phrases(top_stock_sectors[:4], top_mf_categories[:3])

    allocation_summary = _build_allocation_summary(
        v.get("allocation") or {},
        top_stock_sectors,
        top_mf_categories,
        risk_assets,
        nw,
        cash,
    )

    portfolio_focus: dict[str, Any] = {
        "allocationSummary": allocation_summary,
        "topStockSectors": top_stock_sectors,
        "topMfCategories": top_mf_categories,
        "themeSearchPhrases": theme_search_phrases,
        "riskAssetsTotal": round(risk_assets, 0),
        "cash": round(cash, 0),
        "netWorth": round(nw, 0),
    }

    return {
        "tickers": tickers,
        "fund_labels": fund_labels[:MAX_MF_LINES_TO_ENRICH],
        "mf_holding_stock_names": mf_holding_names,
        "portfolioFocus": portfolio_focus,
        "themeSearchPhrases": theme_search_phrases,
    }


def _build_theme_search_phrases(
    stock_sectors: list[dict[str, Any]],
    mf_cats: list[dict[str, Any]],
) -> list[str]:
    """Short OR-query friendly phrases biased to India / portfolio tilt."""
    phrases: list[str] = []
    seen: set[str] = set()

    def add(p: str) -> None:
        p = re.sub(r"\s+", " ", p.strip())[:90]
        if len(p) < 6 or p.lower() in seen:
            return
        seen.add(p.lower())
        phrases.append(p)

    for row in stock_sectors:
        s = str(row.get("sector") or "").strip()
        if not s or s == "Unclassified equity":
            continue
        add(f"India {s} sector stocks")
        if len(phrases) >= 5:
            break

    for row in mf_cats:
        c = str(row.get("category") or "").strip()
        if not c or c == "General / other":
            continue
        add(f"India {c} mutual fund")
        if len(phrases) >= 6:
            break

    if not phrases:
        add("India Nifty sector rotation")
        add("India RBI policy markets")

    return phrases[:6]


def _build_allocation_summary(
    allocation: dict[str, Any],
    top_stock_sectors: list[dict[str, Any]],
    top_mf_categories: list[dict[str, Any]],
    risk_assets: float,
    net_worth: float,
    cash: float,
) -> str:
    eq_pct = round(float(allocation.get("equity") or 0) * 100, 1)
    mf_pct = round(float(allocation.get("mutualFunds") or 0) * 100, 1)
    cash_pct = round(float(allocation.get("cash") or 0) * 100, 1)

    parts = [
        f"Overall mix (by current value): about {eq_pct}% direct equity, {mf_pct}% mutual funds, {cash_pct}% cash."
    ]
    if top_stock_sectors:
        top = top_stock_sectors[0]
        parts.append(
            f"Largest equity sector exposure: {top['sector']} (~{top['pctOfRiskAssets']}% of equity+MF value)."
        )
    if top_mf_categories:
        c0 = top_mf_categories[0]
        parts.append(
            f"Leading mutual-fund style by value: {c0['category']} (~{c0['pctOfRiskAssets']}% of equity+MF value)."
        )
    if risk_assets > 0 and net_worth > 0:
        parts.append(
            f"Investable risk assets (stocks + MFs) are about {_pct(risk_assets, net_worth)}% of net worth (₹{risk_assets:,.0f} of ₹{net_worth:,.0f})."
        )
    return " ".join(parts)


def micro_query_terms(ctx: dict[str, Any]) -> list[str]:
    """Theme phrases first, then tickers, then MF underlying names (OR-query batches)."""
    terms: list[str] = []
    seen: set[str] = set()

    for p in ctx.get("themeSearchPhrases") or []:
        u = str(p).strip()
        if u and u.lower() not in seen:
            seen.add(u.lower())
            terms.append(u)

    for t in ctx.get("tickers") or []:
        u = str(t).strip().upper()
        if u and u not in seen:
            seen.add(u)
            terms.append(u)

    for n in ctx.get("mf_holding_stock_names") or []:
        u = str(n).strip()
        if u and u.lower() not in seen:
            seen.add(u.lower())
            terms.append(u)

    if not terms:
        terms = ["NIFTY", "SENSEX", "India stock market"]
    return terms


def strong_scoring_tokens(ctx: dict[str, Any]) -> list[str]:
    """Higher-weight tokens: theme phrases + sector/category labels."""
    out: list[str] = []
    focus = ctx.get("portfolioFocus") or {}
    for p in ctx.get("themeSearchPhrases") or []:
        out.append(str(p).lower())
        for w in re.split(r"[^\w]+", str(p).lower()):
            if len(w) >= 4:
                out.append(w)
    for row in focus.get("topStockSectors") or []:
        s = str(row.get("sector") or "").lower()
        if s:
            out.append(s)
            for w in s.split():
                if len(w) >= 3:
                    out.append(w)
    for row in focus.get("topMfCategories") or []:
        c = str(row.get("category") or "").lower()
        if c:
            out.append(c[:60])
    return list(dict.fromkeys(t for t in out if t))[:45]


def scoring_tokens(ctx: dict[str, Any]) -> list[str]:
    """Lowercase tokens for ranking (holdings); sector/theme matches use strong_scoring_tokens separately."""
    out: list[str] = []
    for t in ctx.get("tickers") or []:
        out.append(str(t).lower())
    for n in ctx.get("mf_holding_stock_names") or []:
        out.append(str(n).lower())
        first = str(n).split()[0].lower()
        if len(first) >= 3:
            out.append(first)
    for f in ctx.get("fund_labels") or []:
        out.append(str(f).lower()[:40])
    return list(dict.fromkeys(t for t in out if t))


def google_finance_links_for_tickers(tickers: list[str]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    for t in tickers[:15]:
        sym = str(t).strip().upper()
        if not sym:
            continue
        links.append({
            "label": f"{sym} (Google Finance)",
            "url": f"https://www.google.com/finance/quote/{sym}:NSE",
        })
    return links
