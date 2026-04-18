# core/auth.py
import hashlib
import hmac

from streamlit_cookies_manager import EncryptedCookieManager

from config.settings import COOKIE_PASSWORD, COOKIE_PREFIX, COOKIE_SECRET_KEY


def get_cookie_manager() -> EncryptedCookieManager:
    """取得加密 Cookie 管理器"""
    return EncryptedCookieManager(
        prefix=COOKIE_PREFIX,
        password=COOKIE_PASSWORD,
    )


def make_token(username: str) -> str:
    """用 HMAC 簽章產生 token"""
    return hmac.new(
        COOKIE_SECRET_KEY.encode(),
        username.encode(),
        hashlib.sha256,
    ).hexdigest()


def verify_token(username: str, token: str) -> bool:
    """驗證 token 是否合法"""
    expected = make_token(username)
    return hmac.compare_digest(expected, token)