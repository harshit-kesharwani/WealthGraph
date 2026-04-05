from fastapi import Depends, HTTPException

from app.auth_firebase import require_user
from app.firestore_service import ensure_user, get_user, merge_user, set_policy
from app.models import Goal, PolicyUpdate
from app.services.execution import new_goal_id

from fastapi import APIRouter

router = APIRouter(prefix="/policy", tags=["policy"])


@router.get("")
def get_policy(uid: str = Depends(require_user)):
    ensure_user(uid)
    u = get_user(uid) or {}
    return u.get("policy", {})


@router.put("")
def put_policy(body: PolicyUpdate, uid: str = Depends(require_user)):
    ensure_user(uid)
    u = get_user(uid) or {}
    pol = dict(u.get("policy") or {})
    if body.goals is not None:
        goals = []
        for g in body.goals:
            gid = g.id or new_goal_id()
            goals.append(
                {
                    "id": gid,
                    "name": g.name,
                    "targetAmount": g.target_amount,
                    "targetYear": g.target_year,
                }
            )
        pol["goals"] = goals
    if body.max_drawdown_pct is not None:
        pol["maxDrawdownPct"] = body.max_drawdown_pct
    if body.monthly_income is not None:
        pol["monthlyIncome"] = body.monthly_income
    if body.fixed_expenses is not None:
        pol["fixedExpenses"] = body.fixed_expenses
    if body.min_bank_buffer is not None:
        pol["minBankBuffer"] = body.min_bank_buffer
    if body.current_account_balance is not None:
        pol["currentAccountBalance"] = body.current_account_balance
    if body.risk_profile is not None:
        pol["riskProfile"] = body.risk_profile
    set_policy(uid, pol)
    # Autopilot is not available yet; never enable from API.
    if body.autopilot is not None:
        merge_user(uid, {"autopilot": False})
    u2 = get_user(uid) or {}
    return {"policy": u2.get("policy"), "autopilot": False}
