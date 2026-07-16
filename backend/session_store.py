"""
Minimal server-side session store.

Design choice: OAuth access/refresh tokens are kept ONLY on the server,
in this in-memory dict. The browser only ever holds a random, signed
session id in an httponly cookie, so tokens are never exposed to
client-side JS or visible in the cookie itself.

Limitation (documented, not hidden): this is in-memory, so it does not
survive a process restart and does not work across multiple backend
replicas without a shared store (Redis, etc.). That's an intentional
scope cut for a prototype -- flagged here so future-you fixes it before
a real multi-instance production deployment.
"""
import time
import uuid
from typing import Optional, Dict, Any

from itsdangerous import URLSafeSerializer, BadSignature

if __package__:
    from .config import settings
else:
    from config import settings

_serializer = URLSafeSerializer(settings.SESSION_SECRET, salt="aiops-session")

# session_id -> {"credentials": {...}, "email": str, "project_id": str|None, "created": float}
_STORE: Dict[str, Dict[str, Any]] = {}


def create_session(data: Dict[str, Any]) -> str:
    session_id = uuid.uuid4().hex
    data["created"] = time.time()
    _STORE[session_id] = data
    return _serializer.dumps(session_id)


def _resolve_session_id(cookie_value: Optional[str]) -> Optional[str]:
    if not cookie_value:
        return None
    try:
        return _serializer.loads(cookie_value)
    except BadSignature:
        return None


def get_session(cookie_value: Optional[str]) -> Optional[Dict[str, Any]]:
    session_id = _resolve_session_id(cookie_value)
    if session_id is None or session_id not in _STORE:
        return None
    session = _STORE[session_id]
    if time.time() - session["created"] > settings.SESSION_TTL_SECONDS:
        _STORE.pop(session_id, None)
        return None
    return session


def update_session(cookie_value: str, **fields) -> None:
    session_id = _resolve_session_id(cookie_value)
    if session_id and session_id in _STORE:
        _STORE[session_id].update(fields)


def delete_session(cookie_value: Optional[str]) -> None:
    session_id = _resolve_session_id(cookie_value)
    if session_id:
        _STORE.pop(session_id, None)
