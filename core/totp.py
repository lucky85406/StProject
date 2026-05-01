# core/totp.py
"""
Google Authenticator (TOTP) 工具模組
使用 pyotp 實作 RFC 6238 TOTP，與 Google Authenticator 完全相容。
"""
from __future__ import annotations

import io
import logging

import pyotp
import qrcode
from PIL import Image

logger = logging.getLogger("core.totp")


def generate_secret() -> str:
    """
    產生 Base32 隨機秘鑰（32 字元）。
    僅在使用者第一次啟用時呼叫，結果存入 Supabase。
    """
    return pyotp.random_base32()


def get_provisioning_uri(secret: str, username: str, issuer: str = "StProject") -> str:
    """
    產生 otpauth:// URI，供 Google Authenticator 掃描。
    格式：otpauth://totp/StProject:admin?secret=XXX&issuer=StProject
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=username, issuer_name=issuer)


def generate_setup_qr_png(secret: str, username: str) -> bytes:
    """
    產生 TOTP 設定用 QR Code（PNG bytes），直接傳入 st.image()。
    box_size=6 在 Streamlit 中約 200px，適合手機掃描。
    """
    uri = get_provisioning_uri(secret, username)
    qr = qrcode.QRCode(
        box_size=6, border=3, error_correction=qrcode.constants.ERROR_CORRECT_H
    )
    qr.add_data(uri)
    qr.make(fit=True)
    img: Image.Image = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def verify_code(secret: str, code: str) -> bool:
    """
    驗證使用者輸入的 6 位數 TOTP 碼。
    valid_window=1：允許前後各 30 秒的時鐘漂移（共 90 秒有效窗口）。
    """
    if not secret or not code:
        return False
    code = code.strip()
    if len(code) != 6 or not code.isdigit():
        return False
    try:
        totp = pyotp.TOTP(secret)
        result = totp.verify(code, valid_window=1)
        logger.info("TOTP 驗證 ─ result=%s", result)
        return result
    except Exception as e:
        logger.warning("TOTP 驗證例外 ─ error=%s", e)
        return False
