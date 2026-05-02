# core/qr_store.py  ← 修改後完整版
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Literal, Optional

_QR_STORE_FILE = Path(".qr_store.json")
_QR_TTL_SECONDS = 120

QrStatus = Literal["pending", "confirmed", "expired"]


def _load() -> dict:
    if not _QR_STORE_FILE.exists():
        return {}
    try:
        return json.loads(_QR_STORE_FILE.read_text())
    except Exception:
        return {}


def _save(data: dict) -> None:
    _QR_STORE_FILE.write_text(json.dumps(data))


def create_qr_token() -> str:
    """建立新的 QR Token，回傳 token_id"""
    data = _load()
    token_id = str(uuid.uuid4())
    data[token_id] = {
        "status": "pending",
        "username": None,
        "device_hash": None,  # ← 新增：綁定的設備 hash
        "created_at": time.time(),
    }
    _save(data)
    return token_id


def confirm_qr_token(
    token_id: str,
    username: str,
    device_hash: Optional[str] = None,  # ← 新增參數
) -> bool:
    """
    手機端掃描後呼叫：確認 Token 並綁定使用者與設備 hash。
    回傳 True 表示成功，False 表示 Token 無效或已過期。
    """
    data = _load()
    record = data.get(token_id)
    if not record:
        return False
    if time.time() - record["created_at"] > _QR_TTL_SECONDS:
        _expire_token(token_id, data)
        return False
    if record["status"] != "pending":
        return False

    record["status"] = "confirmed"
    record["username"] = username
    record["device_hash"] = device_hash  # ← 新增
    record["confirmed_at"] = time.time()
    data[token_id] = record
    _save(data)
    return True


def check_qr_token(token_id: str) -> tuple[QrStatus, str | None]:
    """瀏覽器輪詢用：回傳 (status, username)"""
    data = _load()
    record = data.get(token_id)
    if not record:
        return "expired", None
    if time.time() - record["created_at"] > _QR_TTL_SECONDS:
        _expire_token(token_id, data)
        return "expired", None
    return record["status"], record.get("username")


def consume_qr_token(token_id: str) -> None:
    """登入成功後清除 Token，防止重複使用"""
    data = _load()
    data.pop(token_id, None)
    _save(data)


def _expire_token(token_id: str, data: dict) -> None:
    if token_id in data:
        data[token_id]["status"] = "expired"
        _save(data)
