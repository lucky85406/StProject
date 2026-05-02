# core/device_auth.py
"""
設備綁定驗證模組
- 使用 SHA-256 對設備指紋字串做雜湊，存入 Supabase user_devices 資料表
- 不儲存原始指紋，僅儲存 hash（隱私保護）
"""
from __future__ import annotations

import hashlib
import logging
from typing import Optional

from core.db import get_client

logger = logging.getLogger("core.device_auth")


# ── 指紋計算 ─────────────────────────────────────────────────────────────────


def compute_device_hash(fingerprint_raw: str) -> str:
    """
    將瀏覽器收集到的原始指紋字串（user-agent|platform|timezone|...）
    做 SHA-256，回傳 64 字元 hex string。
    """
    if not fingerprint_raw or not fingerprint_raw.strip():
        raise ValueError("指紋字串不可為空")
    return hashlib.sha256(fingerprint_raw.strip().encode("utf-8")).hexdigest()


# ── 設備查詢 ─────────────────────────────────────────────────────────────────


def verify_device(username: str, device_hash: str) -> bool:
    """
    驗證該 username 是否有對應的已信任設備 hash。
    回傳 True → 設備已綁定且啟用；False → 未綁定或已撤銷。
    """
    if not username or not device_hash:
        return False
    try:
        client = get_client()
        result = (
            client.table("user_devices")
            .select("id, last_used_at")
            .eq("username", username)
            .eq("device_hash", device_hash)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if not result.data:
            logger.warning("設備驗證失敗 ─ 設備未綁定  user=%s", username)
            return False

        # 更新最後使用時間
        device_id: int = result.data[0]["id"]
        _touch_last_used(device_id)
        logger.info("設備驗證成功 ─ user=%s  device_id=%s", username, device_id)
        return True

    except Exception as exc:
        logger.error("設備驗證例外 ─ user=%s  error=%s", username, exc)
        return False


def _touch_last_used(device_id: int) -> None:
    """非同步更新 last_used_at（失敗不影響主流程）"""
    try:
        from datetime import timezone, datetime

        client = get_client()
        client.table("user_devices").update(
            {"last_used_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", device_id).execute()
    except Exception as exc:
        logger.warning("last_used_at 更新失敗 ─ device_id=%s  error=%s", device_id, exc)


# ── 設備綁定 ─────────────────────────────────────────────────────────────────


def register_device(
    username: str,
    device_hash: str,
    device_label: str = "行動設備",
) -> tuple[bool, str]:
    """
    綁定設備到指定使用者。
    若該 hash 已存在（且 is_active=True）則視為重複綁定，回傳 (False, "already_bound")。

    Returns:
        (True,  "ok")            ─ 綁定成功
        (False, "already_bound") ─ 設備已綁定
        (False, "db_error")      ─ 資料庫錯誤
    """
    if not username or not device_hash:
        return False, "db_error"

    # 先檢查是否已存在
    if verify_device(username, device_hash):
        return False, "already_bound"

    try:
        client = get_client()
        client.table("user_devices").insert(
            {
                "username": username,
                "device_hash": device_hash,
                "device_label": device_label[:50],  # 截斷防止過長
                "is_active": True,
            }
        ).execute()
        logger.info("設備綁定成功 ─ user=%s  label=%s", username, device_label)
        return True, "ok"

    except Exception as exc:
        logger.error("設備綁定失敗 ─ user=%s  error=%s", username, exc)
        return False, "db_error"


# ── 設備管理 ─────────────────────────────────────────────────────────────────


def list_devices(username: str) -> list[dict]:
    """
    列出使用者所有已啟用設備，供設定頁面顯示。
    回傳欄位：id, device_label, created_at, last_used_at
    """
    try:
        client = get_client()
        result = (
            client.table("user_devices")
            .select("id, device_label, created_at, last_used_at")
            .eq("username", username)
            .eq("is_active", True)
            .order("created_at", desc=True)
            .execute()
        )
        return result.data or []
    except Exception as exc:
        logger.error("列出設備失敗 ─ user=%s  error=%s", username, exc)
        return []


def revoke_device(device_id: int, username: str) -> bool:
    """
    撤銷指定設備（軟刪除，is_active 設 False）。
    必須同時傳 username 防止越權撤銷他人設備。
    """
    try:
        client = get_client()
        client.table("user_devices").update({"is_active": False}).eq(
            "id", device_id
        ).eq("username", username).execute()
        logger.info("設備已撤銷 ─ device_id=%s  user=%s", device_id, username)
        return True
    except Exception as exc:
        logger.error("設備撤銷失敗 ─ device_id=%s  error=%s", device_id, exc)
        return False


def has_any_device(username: str) -> bool:
    """快速檢查該使用者是否已有任何已綁定設備"""
    try:
        client = get_client()
        result = (
            client.table("user_devices")
            .select("id")
            .eq("username", username)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        return bool(result.data)
    except Exception:
        return False
