from fastapi import APIRouter, Depends

from app.auth_firebase import require_user
from app.firestore_service import ensure_user, get_user, merge_user
from app.models import ProfileUpdate

router = APIRouter(prefix="/me", tags=["user"])


@router.get("")
def me(uid: str = Depends(require_user)):
    u = ensure_user(uid)
    return _public_user(u)


@router.patch("")
def patch_me(body: ProfileUpdate, uid: str = Depends(require_user)):
    ensure_user(uid)
    patch: dict = {}
    if body.display_name is not None:
        patch["displayName"] = body.display_name
    if body.phone is not None:
        patch["phone"] = body.phone
    if body.is_demo is not None:
        patch["isDemo"] = body.is_demo
    if patch:
        merge_user(uid, patch)
    return _public_user(get_user(uid))


def _public_user(u: dict | None) -> dict:
    if not u:
        return {}
    return {
        "displayName": u.get("displayName", ""),
        "phone": u.get("phone", ""),
        "autopilot": False,
        "isDemo": u.get("isDemo", False),
        "policy": u.get("policy", {}),
        "portfolio": u.get("portfolio", {}),
    }
