from datetime import datetime, timezone
from typing import Any

from google.cloud import firestore

from app.config import get_settings

_client: firestore.Client | None = None


def db() -> firestore.Client:
    global _client
    if _client is None:
        s = get_settings()
        pid = (s.firebase_project_id or s.gcp_project_id or None) or None
        _client = firestore.Client(project=pid)
    return _client


def _user_ref(uid: str):
    return db().collection("users").document(uid)


def default_user_doc(uid: str, email: str | None = None) -> dict[str, Any]:
    return {
        "displayName": "",
        "phone": "",
        "email": email or "",
        "autopilot": False,
        "isDemo": False,
        "policy": {
            "goals": [],
            "maxDrawdownPct": 15.0,
            "monthlyIncome": 0.0,
            "fixedExpenses": 0.0,
            "minBankBuffer": 0.0,
        },
        "portfolio": {
            "cash": 0.0,
            "priceMultiplier": 1.0,
            "stocks": [],
            "mutualFunds": [],
            "lastPrices": {},
        },
        "updatedAt": firestore.SERVER_TIMESTAMP,
    }


def get_user(uid: str) -> dict[str, Any] | None:
    snap = _user_ref(uid).get()
    if not snap.exists:
        return None
    return snap.to_dict()


def ensure_user(uid: str, email: str | None = None) -> dict[str, Any]:
    ref = _user_ref(uid)
    snap = ref.get()
    if snap.exists:
        return snap.to_dict()  # type: ignore
    data = default_user_doc(uid, email)
    ref.set(data)
    snap = ref.get()
    return snap.to_dict()  # type: ignore


def merge_user(uid: str, updates: dict[str, Any]) -> None:
    updates = {**updates, "updatedAt": firestore.SERVER_TIMESTAMP}
    _user_ref(uid).set(updates, merge=True)


def set_portfolio(uid: str, portfolio: dict[str, Any]) -> None:
    _user_ref(uid).update({"portfolio": portfolio, "updatedAt": firestore.SERVER_TIMESTAMP})


def set_policy(uid: str, policy: dict[str, Any]) -> None:
    _user_ref(uid).update({"policy": policy, "updatedAt": firestore.SERVER_TIMESTAMP})


def add_alert(uid: str, title: str, body: str) -> str:
    col = _user_ref(uid).collection("alerts")
    doc = col.document()
    doc.set(
        {
            "title": title,
            "body": body,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "read": False,
        }
    )
    return doc.id


def add_trade_log(uid: str, payload: dict[str, Any]) -> str:
    col = _user_ref(uid).collection("trades")
    doc = col.document()
    doc.set(
        {
            **payload,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "status": "simulated_success",
        }
    )
    return doc.id


def add_pending_proposal(uid: str, proposal: dict[str, Any]) -> str:
    col = _user_ref(uid).collection("pending_actions")
    doc = col.document()
    doc.set(
        {**proposal, "status": "pending", "createdAt": datetime.now(timezone.utc).isoformat()}
    )
    return doc.id


def get_pending_proposals(uid: str) -> list[dict[str, Any]]:
    col = _user_ref(uid).collection("pending_actions")
    out = []
    for d in col.where("status", "==", "pending").stream():
        data = d.to_dict() or {}
        data["id"] = d.id
        out.append(data)
    return out


def resolve_proposal(uid: str, proposal_id: str, approved: bool) -> bool:
    ref = _user_ref(uid).collection("pending_actions").document(proposal_id)
    snap = ref.get()
    if not snap.exists:
        return False
    ref.update({"status": "approved" if approved else "rejected"})
    return True


def get_proposal(uid: str, proposal_id: str) -> dict[str, Any] | None:
    ref = _user_ref(uid).collection("pending_actions").document(proposal_id)
    snap = ref.get()
    if not snap.exists:
        return None
    d = snap.to_dict() or {}
    d["id"] = snap.id
    return d


def list_alerts(uid: str, limit: int = 50) -> list[dict[str, Any]]:
    col = _user_ref(uid).collection("alerts")
    out = []
    try:
        q = col.order_by("createdAt", direction=firestore.Query.DESCENDING).limit(limit)
        for d in q.stream():
            data = d.to_dict() or {}
            data["id"] = d.id
            out.append(data)
    except Exception:
        for d in col.limit(limit).stream():
            data = d.to_dict() or {}
            data["id"] = d.id
            out.append(data)
    return out


def list_trades(uid: str, limit: int = 50) -> list[dict[str, Any]]:
    col = _user_ref(uid).collection("trades")
    out = []
    try:
        q = col.order_by("createdAt", direction=firestore.Query.DESCENDING).limit(limit)
        for d in q.stream():
            data = d.to_dict() or {}
            data["id"] = d.id
            out.append(data)
    except Exception:
        for d in col.limit(limit).stream():
            data = d.to_dict() or {}
            data["id"] = d.id
            out.append(data)
    return out


def _advisor_threads_col(uid: str):
    return _user_ref(uid).collection("advisor_threads")


def create_advisor_thread(uid: str) -> str:
    """Create an empty Live Advisor thread. Returns document id."""
    col = _advisor_threads_col(uid)
    doc = col.document()
    now = datetime.now(timezone.utc).isoformat()
    doc.set(
        {
            "title": "New chat",
            "messages": [],
            "createdAt": now,
            "updatedAt": now,
        }
    )
    return doc.id


def list_advisor_threads(uid: str, limit: int = 50) -> list[dict[str, Any]]:
    """List thread summaries for sidebar (no message bodies)."""
    col = _advisor_threads_col(uid)
    out: list[dict[str, Any]] = []
    try:
        q = col.order_by("updatedAt", direction=firestore.Query.DESCENDING).limit(limit)
        for d in q.stream():
            data = d.to_dict() or {}
            out.append(
                {
                    "id": d.id,
                    "title": str(data.get("title") or "Chat"),
                    "updatedAt": data.get("updatedAt") or data.get("createdAt") or "",
                }
            )
    except Exception:
        for d in col.limit(limit).stream():
            data = d.to_dict() or {}
            out.append(
                {
                    "id": d.id,
                    "title": str(data.get("title") or "Chat"),
                    "updatedAt": data.get("updatedAt") or data.get("createdAt") or "",
                }
            )
        out.sort(key=lambda x: str(x.get("updatedAt") or ""), reverse=True)
        out = out[:limit]
    return out


def get_advisor_thread(uid: str, thread_id: str) -> dict[str, Any] | None:
    ref = _advisor_threads_col(uid).document(thread_id)
    snap = ref.get()
    if not snap.exists:
        return None
    d = snap.to_dict() or {}
    d["id"] = snap.id
    if not isinstance(d.get("messages"), list):
        d["messages"] = []
    return d


def save_advisor_thread_messages(
    uid: str,
    thread_id: str,
    messages: list[dict[str, Any]],
    title: str | None = None,
) -> None:
    """Replace thread messages and bump updatedAt; optionally set title."""
    ref = _advisor_threads_col(uid).document(thread_id)
    now = datetime.now(timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "messages": messages[-32:],
        "updatedAt": now,
    }
    if title is not None:
        payload["title"] = title
    ref.update(payload)


def clear_subcollection(uid: str, subcollection: str) -> int:
    """Delete all documents in a user's subcollection. Returns count deleted."""
    col = _user_ref(uid).collection(subcollection)
    count = 0
    batch_size = 100
    while True:
        docs = list(col.limit(batch_size).stream())
        if not docs:
            break
        batch = db().batch()
        for d in docs:
            batch.delete(d.reference)
            count += 1
        batch.commit()
    return count
