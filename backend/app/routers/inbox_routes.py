from fastapi import APIRouter, Depends

from app.auth_firebase import require_user
from app.firestore_service import (
    clear_subcollection,
    ensure_user,
    get_pending_proposals,
    list_alerts,
    list_trades,
)

router = APIRouter(prefix="/inbox", tags=["inbox"])


@router.get("/alerts")
def inbox_alerts(uid: str = Depends(require_user)):
    ensure_user(uid)
    return {"items": list_alerts(uid)}


@router.get("/trades")
def inbox_trades(uid: str = Depends(require_user)):
    ensure_user(uid)
    return {"items": list_trades(uid)}


@router.get("/pending")
def inbox_pending(uid: str = Depends(require_user)):
    ensure_user(uid)
    return {"items": get_pending_proposals(uid)}


@router.delete("/all")
def clear_all_updates(uid: str = Depends(require_user)):
    """Clear all alerts, trades, and pending actions for the user."""
    ensure_user(uid)
    a = clear_subcollection(uid, "alerts")
    t = clear_subcollection(uid, "trades")
    p = clear_subcollection(uid, "pending_actions")
    return {"deleted": {"alerts": a, "trades": t, "pending_actions": p}}
