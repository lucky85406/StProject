# core/users.py
from __future__ import annotations
import logging
import bcrypt
from core.db import get_client
from typing import Literal
from core.totp import verify_code

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


def user_exists(username: str) -> bool:
    """
    ✅ QR 登入用：確認使用者是否存在於 Supabase users table。
    僅查詢 username 欄位，不涉及密碼，回傳布林值。
    找不到使用者（PostgREST PGRST116）或任何例外都視為不存在。
    """
    if not username or not username.strip():
        return False
    try:
        client = get_client()
        result = (
            client.table("users")
            .select("username")
            .eq("username", username.strip())
            .single()  # 找不到時會 raise APIError (code PGRST116)
            .execute()
        )
        exists = result.data is not None
        logger.info("使用者存在性查詢 ─ user=%s  exists=%s", username, exists)
        return exists
    except Exception as e:
        logger.warning("使用者存在性查詢失敗 ─ user=%s  error=%s", username, e)
        return False


def create_user(username: str, password: str) -> bool:
    """
    新增使用者（管理功能用）。
    totp_enabled 預設 False，新使用者首次登入時會被引導至設定閘門。
    """
    try:
        client = get_client()
        client.table("users").insert(
            {
                "username": username,
                "password": _hash_password(password),
                "totp_enabled": False,  # 明確帶入，語意清晰
                "totp_secret": None,
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

# ── 以下四個函式追加至檔案末尾 ────────────────────────────────────

LoginReason = Literal[
    "ok", "wrong_password", "totp_required", "wrong_totp", "not_found"
]


def get_totp_info(username: str) -> tuple[bool, str | None]:
    """
    查詢該使用者的 TOTP 狀態。
    回傳 (totp_enabled, totp_secret)；
    若使用者不存在或查詢失敗，回傳 (False, None)。
    """
    try:
        client = get_client()
        result = (
            client.table("users")
            .select("totp_enabled, totp_secret")
            .eq("username", username)
            .single()
            .execute()
        )
        enabled: bool = result.data.get("totp_enabled", False)
        secret: str | None = result.data.get("totp_secret")
        return enabled, secret
    except Exception as e:
        logger.warning("TOTP 狀態查詢失敗 ─ user=%s  error=%s", username, e)
        return False, None


def save_totp_secret(username: str, secret: str) -> bool:
    """
    儲存 TOTP 秘鑰並啟用 TOTP（settings 頁面設定流程用）。
    """
    try:
        client = get_client()
        client.table("users").update({"totp_secret": secret, "totp_enabled": True}).eq(
            "username", username
        ).execute()
        logger.info("TOTP 秘鑰已儲存並啟用 ─ user=%s", username)
        return True
    except Exception as e:
        logger.error("TOTP 秘鑰儲存失敗 ─ user=%s  error=%s", username, e)
        return False


def disable_totp(username: str) -> bool:
    """
    停用 TOTP 並清除秘鑰。
    """
    try:
        client = get_client()
        client.table("users").update({"totp_secret": None, "totp_enabled": False}).eq(
            "username", username
        ).execute()
        logger.info("TOTP 已停用 ─ user=%s", username)
        return True
    except Exception as e:
        logger.error("TOTP 停用失敗 ─ user=%s  error=%s", username, e)
        return False


def verify_login(
    username: str, password: str, totp_code: str = ""
) -> tuple[bool, LoginReason]:
    """
    ✅ 統一登入驗證入口（密碼登入 & QR 登入手機端共用）。

    驗證流程：
      1. bcrypt 密碼比對
      2. 若 totp_enabled=True → 驗證 6 位數碼
      3. 若 totp_enabled=False → totp_code 傳空亦可通過

    回傳:
      (True,  "ok")            ─ 登入成功
      (False, "wrong_password") ─ 密碼錯誤
      (False, "totp_required")  ─ 需要 TOTP 但未輸入
      (False, "wrong_totp")     ─ TOTP 碼錯誤
      (False, "not_found")      ─ 使用者不存在
    """
    try:
        client = get_client()
        result = (
            client.table("users")
            .select("password, totp_enabled, totp_secret")
            .eq("username", username)
            .single()
            .execute()
        )
    except Exception as e:
        logger.warning("登入查詢失敗 ─ user=%s  error=%s", username, e)
        return False, "not_found"

    row = result.data

    # ── Step 1: 密碼驗證 ──────────────────────────────────────────
    stored_hash: str = row.get("password", "")
    import bcrypt  # 局部 import 避免頂層循環

    if not bcrypt.checkpw(password.encode(), stored_hash.encode()):
        logger.warning("登入失敗 ─ 密碼錯誤  user=%s", username)
        return False, "wrong_password"

    # ── Step 2: TOTP 驗證（若已啟用）────────────────────────────
    totp_enabled: bool = row.get("totp_enabled", False)
    totp_secret: str | None = row.get("totp_secret")

    if totp_enabled:
        if not totp_code or not totp_code.strip():
            logger.warning("登入失敗 ─ TOTP 未輸入  user=%s", username)
            return False, "totp_required"
        if not verify_code(totp_secret or "", totp_code.strip()):
            logger.warning("登入失敗 ─ TOTP 錯誤  user=%s", username)
            return False, "wrong_totp"

    logger.info("登入成功 ─ user=%s  totp_used=%s", username, totp_enabled)
    return True, "ok"
