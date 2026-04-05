from fastapi import APIRouter, Depends, HTTPException

from app.auth_firebase import require_user
from app.firestore_service import ensure_user, get_user, set_portfolio

from app.models import DemoCrashRequest, DemoSalaryRequest

router = APIRouter(prefix="/demo", tags=["demo"])


def _require_demo(uid: str):
    u = get_user(uid) or {}
    if not u.get("isDemo"):
        raise HTTPException(403, "Demo endpoints require isDemo on your profile (PATCH /me).")
    return u


@router.post("/inject-salary")
def inject_salary(body: DemoSalaryRequest, uid: str = Depends(require_user)):
    ensure_user(uid)
    _require_demo(uid)
    u = get_user(uid) or {}
    p = dict(u.get("portfolio") or {})
    cash = float(p.get("cash", 0)) + body.amount_inr
    p["cash"] = cash
    set_portfolio(uid, p)
    return {"ok": True, "cash": cash}


@router.post("/simulate-crash")
def simulate_crash(body: DemoCrashRequest, uid: str = Depends(require_user)):
    ensure_user(uid)
    _require_demo(uid)
    u = get_user(uid) or {}
    p = dict(u.get("portfolio") or {})
    mult = 1.0 - (body.drop_pct / 100.0)
    cur = float(p.get("priceMultiplier", 1.0))
    p["priceMultiplier"] = cur * mult
    set_portfolio(uid, p)
    return {"ok": True, "priceMultiplier": p["priceMultiplier"]}
