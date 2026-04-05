"""Live valuation: yfinance, mftool, Firestore lastPrices fallback."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import yfinance as yf
from mftool import Mftool

from app.services.amfi_nav import fetch_mf_nav_by_isin, lookup_isin_meta

logger = logging.getLogger(__name__)
_mf = Mftool()


def _normalize_equity_ticker(ticker: str) -> str:
    t = ticker.strip().upper()
    if "." not in t:
        return f"{t}.NS"
    return t


def fetch_equity_price(ticker: str) -> tuple[float | None, bool]:
    """Returns (price, live_ok)."""
    sym = _normalize_equity_ticker(ticker)
    try:
        tk = yf.Ticker(sym)
        hist = tk.history(period="5d")
        if hist is not None and not hist.empty:
            return float(hist["Close"].iloc[-1]), True
        info = tk.info or {}
        fast = info.get("regularMarketPrice") or info.get("currentPrice")
        if fast:
            return float(fast), True
    except Exception as e:
        logger.warning("yfinance failed for %s: %s", sym, e)
    return None, False


def fetch_equity_history(ticker: str, period: str = "1y") -> list[dict[str, Any]]:
    """Fetch historical closing prices for fundamental analysis."""
    sym = _normalize_equity_ticker(ticker)
    try:
        hist = yf.Ticker(sym).history(period=period)
        if hist is not None and not hist.empty:
            return [
                {"date": str(idx.date()), "close": round(float(row["Close"]), 2)}
                for idx, row in hist.iterrows()
            ]
    except Exception as e:
        logger.warning("yfinance history failed for %s: %s", sym, e)
    return []


def fetch_mf_nav(amfi_code: str) -> tuple[float | None, bool]:
    try:
        q = _mf.get_scheme_quote(str(amfi_code))
        if q and q.get("nav"):
            return float(str(q["nav"]).replace(",", "")), True
    except Exception as e:
        logger.warning("mftool failed for %s: %s", amfi_code, e)
    return None, False


def value_portfolio(
    portfolio: dict[str, Any],
    last_prices_fallback: dict[str, float],
) -> dict[str, Any]:
    """
    Enrich portfolio with current prices, P&L, allocation, approximate return.
    Applies priceMultiplier for demo crash simulation on equity/MF marks.
    """
    mult = float(portfolio.get("priceMultiplier") or 1.0)
    stocks = portfolio.get("stocks") or []
    mfs = portfolio.get("mutualFunds") or []
    cash = float(portfolio.get("cash") or 0)
    last_known = dict(portfolio.get("lastPrices") or {})
    last_known.update(last_prices_fallback)

    equity_lines: list[dict[str, Any]] = []
    mf_lines: list[dict[str, Any]] = []
    warnings: list[str] = []
    new_last: dict[str, float] = dict(last_known)

    total_invested = 0.0
    total_current = cash

    for s in stocks:
        t = s.get("ticker", "")
        qty = float(s.get("qty", 0))
        buy = float(s.get("buyPrice", 0))
        invested = qty * buy
        total_invested += invested
        key = f"eq:{_normalize_equity_ticker(t)}"
        price, ok = fetch_equity_price(t)
        if price is None:
            price = last_known.get(key)
            if price is not None:
                warnings.append(f"Using cached price for {t}")
                ok = False
        if price is None:
            warnings.append(f"No price for {t}")
            price = buy
        price_adj = price * mult
        new_last[key] = price
        cur = qty * price_adj
        total_current += cur
        pnl = cur - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
        equity_lines.append(
            {
                "ticker": t,
                "name": s.get("name", t),
                "qty": qty,
                "buyPrice": buy,
                "buyDate": s.get("buyDate"),
                "currentPrice": price_adj,
                "invested": invested,
                "currentValue": cur,
                "pnl": pnl,
                "pnlPct": round(pnl_pct, 2),
                "live": ok,
            }
        )

    for m in mfs:
        code = str(m.get("amfiCode", m.get("amfi_code", "")))
        isin = str(m.get("isin") or m.get("ISIN") or "").strip().upper()
        units = float(m.get("units", 0))
        buy_nav = float(m.get("buyNav", m.get("buy_nav", 0)))
        invested = units * buy_nav
        total_invested += invested
        nav: float | None = None
        nav_date: str | None = None
        ok = False
        key = f"mf:{isin}" if isin else f"mf:{code}"

        if isin:
            nav, nav_date, ok = fetch_mf_nav_by_isin(isin)
            if nav is None and code:
                nav, ok = fetch_mf_nav(code)
        else:
            nav, ok = fetch_mf_nav(code) if code else (None, False)

        if nav is None:
            nav = last_known.get(key)
            if nav is None and isin and code:
                nav = last_known.get(f"mf:{code}")
            if nav is not None:
                warnings.append(f"Using cached NAV for MF {isin or code}")
                ok = False
        if nav is None:
            warnings.append(f"No NAV for MF {isin or code}")
            nav = buy_nav
        nav_adj = nav * mult
        new_last[key] = nav
        cur = units * nav_adj
        total_current += cur
        pnl = cur - invested
        pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
        display_name = (m.get("name") or "").strip()
        if not display_name and isin:
            meta = lookup_isin_meta(isin)
            if meta:
                display_name = meta.get("scheme_name", "")
        if not display_name:
            display_name = code or isin or "Fund"

        mf_lines.append(
            {
                "amfiCode": code,
                "isin": isin or None,
                "name": display_name,
                "units": units,
                "buyNav": buy_nav,
                "buyDate": m.get("buyDate"),
                "currentNav": nav_adj,
                "navDate": nav_date,
                "invested": invested,
                "currentValue": cur,
                "pnl": pnl,
                "pnlPct": round(pnl_pct, 2),
                "live": ok,
            }
        )

    pnl_total = total_current - total_invested - cash
    approx_return_pct = (pnl_total / total_invested * 100) if total_invested > 0 else 0.0

    alloc_equity = sum(x["currentValue"] for x in equity_lines)
    alloc_mf = sum(x["currentValue"] for x in mf_lines)
    denom = alloc_equity + alloc_mf + cash
    allocation = {
        "equity": (alloc_equity / denom) if denom else 0,
        "mutualFunds": (alloc_mf / denom) if denom else 0,
        "cash": (cash / denom) if denom else 0,
    }

    return {
        "netWorth": total_current,
        "totalInvested": total_invested,
        "cash": cash,
        "totalPnl": pnl_total,
        "approxReturnPct": approx_return_pct,
        "xirrNote": "Estimated from portfolio values; personalized money-weighted return not shown.",
        "approxReturnPctLabeled": approx_return_pct,
        "equity": equity_lines,
        "mutualFunds": mf_lines,
        "allocation": allocation,
        "priceWarnings": warnings,
        "lastPrices": new_last,
    }
