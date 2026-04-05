from fastapi import APIRouter, Depends, HTTPException

from app.auth_firebase import require_user
from app.firestore_service import (
    add_alert,
    add_trade_log,
    ensure_user,
    get_user,
    get_proposal,
    resolve_proposal,
    set_portfolio,
)
from app.models import ProposalDecision, SimulateTradeRequest
from app.services.execution import apply_buy_mf, apply_buy_stock
from app.services.valuation import _normalize_equity_ticker, value_portfolio

router = APIRouter(tags=["trades", "inbox"])


@router.post("/trades/simulate")
def simulate_trade(body: SimulateTradeRequest, uid: str = Depends(require_user)):
    ensure_user(uid)
    u = get_user(uid) or {}
    p = dict(u.get("portfolio") or {})
    if body.side != "buy":
        raise HTTPException(400, "Only buy is supported in this demo.")
    if body.asset_type == "stock":
        p = apply_buy_stock(p, body.symbol, body.qty, body.price)
    else:
        p = apply_buy_mf(p, body.symbol, body.qty, body.price)
    set_portfolio(uid, p)
    tid = add_trade_log(
        uid,
        {
            "symbol": body.symbol,
            "side": body.side,
            "qty": body.qty,
            "price": body.price,
            "asset_type": body.asset_type,
        },
    )
    add_alert(uid, "Trade successful (mock)", f"{body.side} {body.qty} @ {body.price} for {body.symbol}")
    return {"ok": True, "tradeId": tid, "portfolio": p}


@router.post("/proposals/decide")
def decide_proposal(body: ProposalDecision, uid: str = Depends(require_user)):
    ensure_user(uid)
    if not body.approve:
        if not resolve_proposal(uid, body.proposal_id, False):
            raise HTTPException(404, "Proposal not found")
        add_alert(uid, "Proposal rejected", body.proposal_id)
        return {"ok": True, "approved": False}
    prop = get_proposal(uid, body.proposal_id)
    if not prop:
        raise HTTPException(404, "Proposal not found")
    u = get_user(uid) or {}
    p = dict(u.get("portfolio") or {})
    fb = dict(p.get("lastPrices") or {})
    val = value_portfolio(p, fb)
    lastp = val.pop("lastPrices", {})
    p = {**p, "lastPrices": lastp}
    sym = str(prop.get("symbol", ""))
    notional = float(prop.get("notional_inr", 0) or 0)
    price = None
    key = f"eq:{_normalize_equity_ticker(sym)}"
    price = lastp.get(key)
    if price is None:
        for line in val.get("equity") or []:
            if _normalize_equity_ticker(str(line.get("ticker", ""))) == _normalize_equity_ticker(sym):
                price = float(line.get("currentPrice", 0))
                break
    if price is None or price <= 0 or notional <= 0:
        raise HTTPException(400, "Cannot price proposal")
    qty = notional / price
    p = apply_buy_stock(p, sym.split(".")[0] if "." in sym else sym, qty, price)
    set_portfolio(uid, p)
    resolve_proposal(uid, body.proposal_id, True)
    add_trade_log(uid, {"symbol": sym, "side": "buy", "qty": qty, "price": price, "from_proposal": body.proposal_id})
    add_alert(uid, "You approved a trade", f"Simulated buy {sym} ~₹{notional:.0f}")
    return {"ok": True, "approved": True, "portfolio": p}
