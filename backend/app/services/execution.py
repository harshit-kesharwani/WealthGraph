"""Mock trade execution — updates Firestore portfolio only."""

from __future__ import annotations

import uuid
from typing import Any


def apply_buy_stock(portfolio: dict[str, Any], symbol: str, qty: float, price: float) -> dict[str, Any]:
    cost = qty * price
    cash = float(portfolio.get("cash") or 0)
    if cost > cash + 1e-6:
        raise ValueError("Insufficient cash")
    stocks = list(portfolio.get("stocks") or [])
    norm = symbol.upper()
    found = False
    for s in stocks:
        t = str(s.get("ticker", "")).upper()
        if t == norm or t.split(".")[0] == norm.split(".")[0]:
            old_q = float(s.get("qty", 0))
            old_bp = float(s.get("buyPrice", s.get("buy_price", 0)))
            new_q = old_q + qty
            new_bp = (old_bp * old_q + price * qty) / new_q if new_q else price
            s["qty"] = new_q
            s["buyPrice"] = new_bp
            found = True
            break
    if not found:
        stocks.append({"ticker": symbol, "qty": qty, "buyPrice": price})
    portfolio = {**portfolio, "cash": cash - cost, "stocks": stocks}
    return portfolio


def apply_buy_mf(portfolio: dict[str, Any], amfi_code: str, units: float, nav: float) -> dict[str, Any]:
    cost = units * nav
    cash = float(portfolio.get("cash") or 0)
    if cost > cash + 1e-6:
        raise ValueError("Insufficient cash")
    mfs = list(portfolio.get("mutualFunds") or [])
    code = str(amfi_code)
    found = False
    for m in mfs:
        if str(m.get("amfiCode", m.get("amfi_code", ""))) == code:
            old_u = float(m.get("units", 0))
            old_nav = float(m.get("buyNav", m.get("buy_nav", 0)))
            new_u = old_u + units
            new_bn = (old_nav * old_u + nav * units) / new_u if new_u else nav
            m["units"] = new_u
            m["buyNav"] = new_bn
            found = True
            break
    if not found:
        mfs.append({"amfiCode": code, "units": units, "buyNav": nav})
    portfolio = {**portfolio, "cash": cash - cost, "mutualFunds": mfs}
    return portfolio


def new_goal_id() -> str:
    return str(uuid.uuid4())[:8]
