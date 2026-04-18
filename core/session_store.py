# core/session_store.py
import json
import time
import uuid
from pathlib import Path

_STORE_FILE = Path(".session_store.json")
_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 天後過期


def _load() -> dict:
    if not _STORE_FILE.exists():
        return {}
    try:
        return json.loads(_STORE_FILE.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    _STORE_FILE.write_text(json.dumps(data))


def create_session(username: str) -> str:
    """建立新 session，回傳 session_id"""
    data = _load()
    session_id = str(uuid.uuid4())
    data[session_id] = {
        "username": username,
        "created_at": time.time(),
    }
    _save(data)
    return session_id


def verify_session(session_id: str) -> str | None:
    """驗證 session，回傳 username；無效或過期回傳 None"""
    if not session_id:
        return None
    data = _load()
    record = data.get(session_id)
    if not record:
        return None
    if time.time() - record["created_at"] > _TTL_SECONDS:
        delete_session(session_id)
        return None
    return record["username"]


def delete_session(session_id: str) -> None:
    """刪除 session"""
    data = _load()
    data.pop(session_id, None)
    _save(data)
