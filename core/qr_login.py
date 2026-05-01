# core/qr_login.py
"""產生 QR Code 圖片（bytes），供 Streamlit st.image() 顯示"""
from __future__ import annotations

import io

import qrcode
from qrcode.image.pil import PilImage

from core.network import get_app_base_url


def generate_qr_image(url: str, box_size: int = 8) -> bytes:
    """
    將 URL 編碼成 QR Code，回傳 PNG bytes。

    Args:
        url:      要編碼的完整 URL（含 token 參數）
        box_size: 每個方格的像素大小，預設 8
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=3,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img: PilImage = qr.make_image(
        fill_color="#3b3552",
        back_color="#ffffff",
    )
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_confirm_url(token_id: str, port: int = 8501) -> str:
    """
    組合 QR Code 掃描後的確認 URL。
    自動使用內網 IP，讓同 WiFi 的手機可以直接連線。

    Args:
        token_id: QR Token 的唯一識別碼
        port:     Streamlit port，預設 8501

    Returns:
        例如 "http://192.168.1.100:8501/?qr_confirm=xxxx-xxxx"
    """
    base_url = get_app_base_url(port=port)
    return f"{base_url}/?qr_confirm={token_id}"
