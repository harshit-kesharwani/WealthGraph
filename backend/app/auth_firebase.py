import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings

_bearer = HTTPBearer(auto_error=False)
_app_initialized = False


def init_firebase() -> None:
    global _app_initialized
    if _app_initialized:
        return
    s = get_settings()
    if not firebase_admin._apps:
        options = {"projectId": s.firebase_project_id} if s.firebase_project_id else None
        if s.firebase_credentials_path:
            cred = credentials.Certificate(s.firebase_credentials_path)
            if options:
                firebase_admin.initialize_app(cred, options=options)
            else:
                firebase_admin.initialize_app(cred)
        elif options:
            firebase_admin.initialize_app(options=options)
        else:
            firebase_admin.initialize_app()
    _app_initialized = True


async def require_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    init_firebase()
    if not creds or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
        )
    try:
        decoded = auth.verify_id_token(creds.credentials)
        uid = decoded.get("uid")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")
        return uid
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
