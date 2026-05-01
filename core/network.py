# core/network.py
"""
自動偵測本機在區域網路中的 IP 位址。
優先順序：環境變數 APP_BASE_URL → 自動偵測內網 IP → fallback localhost
"""
from __future__ import annotations

import logging
import os
import socket

logger = logging.getLogger("core.network")


def get_local_ip() -> str:
    """
    取得本機在區域網路的 IP（例如 192.168.1.100）。
    原理：建立一個對外的 UDP 連線（不實際發送封包），
    從 socket 取得本機被選中的出口 IP。
    """
    try:
        # 連到任意外部 IP（不需真的通），讓 OS 選擇出口介面
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            local_ip: str = s.getsockname()[0]
        logger.info("偵測到內網 IP：%s", local_ip)
        return local_ip
    except OSError:
        logger.warning("無法偵測內網 IP，fallback 至 127.0.0.1")
        return "127.0.0.1"


def get_app_base_url(port: int = 8501) -> str:
    """
    回傳 Streamlit 應用的完整 Base URL。

    優先順序：
    1. 環境變數 APP_BASE_URL（最高優先，適合正式部署）
    2. 自動偵測內網 IP + port（內網開發環境）
    3. fallback：http://localhost:8501

    Args:
        port: Streamlit 監聽的 port，預設 8501

    Returns:
        完整 URL 字串，例如 "http://192.168.1.100:8501"
    """
    # 優先讀取環境變數
    env_url: str = os.getenv("APP_BASE_URL", "").rstrip("/")
    if env_url:
        logger.info("使用環境變數 APP_BASE_URL：%s", env_url)
        return env_url

    # 自動偵測內網 IP
    local_ip = get_local_ip()
    auto_url = f"http://{local_ip}:{port}"
    logger.info("自動組成內網 URL：%s", auto_url)
    return auto_url
