# core/users.py
from __future__ import annotations
import logging
import bcrypt
from core.db import get_client

logger = logging.getLogger("core.users")


def _hash_password(plain: str) -> str:
    """產生 bcrypt hash（新增使用者時使用）"""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(username: str, password: str) -> bool:
    """
    從 Supabase 查詢使用者，驗證密碼是否正確。
    找不到使用者或密碼錯誤都回傳 False，不透露原因（防止帳號枚舉攻擊）。
    """
    try:
        client = get_client()
        result = (
            client.table("users")
            .select("password")
            .eq("username", username)
            .single()  # 找不到會 raise exception
            .execute()
        )
        stored_hash: str = result.data["password"]
        is_valid = bcrypt.checkpw(password.encode(), stored_hash.encode())
        logger.info("登入驗證 ─ user=%s  result=%s", username, is_valid)
        return is_valid

    except Exception as e:
        logger.warning("登入驗證失敗 ─ user=%s  error=%s", username, e)
        return False


def create_user(username: str, password: str) -> bool:
    """新增使用者（管理功能用）"""
    try:
        client = get_client()
        client.table("users").insert(
            {
                "username": username,
                "password": _hash_password(password),
            }
        ).execute()
        logger.info("使用者建立成功 ─ user=%s", username)
        return True
    except Exception as e:
        logger.error("使用者建立失敗 ─ user=%s  error=%s", username, e)
        return False


def change_password(username: str, old_password: str, new_password: str) -> bool:
    """修改密碼（對應 pages/settings.py 的修改密碼功能）"""
    if not verify_password(username, old_password):
        logger.warning("改密碼失敗 ─ 舊密碼錯誤  user=%s", username)
        return False
    try:
        client = get_client()
        client.table("users").update({"password": _hash_password(new_password)}).eq(
            "username", username
        ).execute()
        logger.info("密碼更新成功 ─ user=%s", username)
        return True
    except Exception as e:
        logger.error("密碼更新失敗 ─ user=%s  error=%s", username, e)
        return False
