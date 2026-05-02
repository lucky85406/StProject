# app.py  ──  StProject 主程式入口
# 架構：登入 → 主畫面（側邊欄導覽 + 動態參數面板 + Footer）+ 全域 Log 系統
from __future__ import annotations

import datetime
import logging
import sys
import os
import warnings
from typing import Any

import streamlit as st

import time
from core.qr_store import (
    create_qr_token,
    check_qr_token,
    consume_qr_token,
    confirm_qr_token,
)
from core.qr_login import generate_qr_image, build_confirm_url

from core.session_store import create_session, verify_session, delete_session
from core.users import verify_password, get_user_id

# ══════════════════════════════════════════════════════════════════════════════
#  全域 Log 設定
#  格式：時間戳 + 層級 + 模組名稱 + 訊息
#  不同功能間以 ══ 符號區隔
# ══════════════════════════════════════════════════════════════════════════════

_LOG_FORMAT = "%(asctime)s  [%(levelname)-8s]  %(name)-24s │  %(message)s"
_LOG_DATE_FMT = "%Y-%m-%d %H:%M:%S"

logging.basicConfig(
    level=logging.INFO,
    format=_LOG_FORMAT,
    datefmt=_LOG_DATE_FMT,
    stream=sys.stdout,
    force=True,  # 覆蓋 Streamlit 預設 handler
)

logger = logging.getLogger("app")

DIVIDER = "═" * 72


def log_section(title: str) -> None:
    """在 CMD 輸出功能區隔橫幅"""
    print(f"\n{DIVIDER}")
    print(f"  ▶  {title.upper()}")
    print(f"{DIVIDER}\n")


# ══════════════════════════════════════════════════════════════════════════════
#  Streamlit 頁面初始設定
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="StProject",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ══════════════════════════════════════════════════════════════════════════════
#  全域 CSS
# ══════════════════════════════════════════════════════════════════════════════

GLOBAL_CSS = """
<style>
/* ── Google Fonts ─────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@300;400;500;600;700;800&family=DM+Mono:wght@400;500&display=swap');

/* ── 設計 Token：柔和淺色漸層系 ──────────────────────────────────── */
:root {
    /* 背景：米白帶粉漸層 */
    --bg:          #f5f3ff;
    --bg-grad:     linear-gradient(145deg, #f0f4ff 0%, #faf5ff 50%, #fff0f9 100%);

    /* 卡片 / 側邊欄 */
    --surface:     #ffffff;
    --surface2:    #f8f6ff;
    --surface3:    #eef2ff;

    /* 邊框 */
    --border:      rgba(139,92,246,0.12);
    --border-hi:   rgba(139,92,246,0.25);

    /* 文字 */
    --text:        #3b3552;
    --text-muted:  #8b85a8;
    --text-light:  #b8b2d0;

    /* 主色調：薰衣草紫 → 玫瑰粉 漸層 */
    --accent:      #7c6ff7;
    --accent2:     #e879a0;
    --accent-soft: rgba(124,111,247,0.12);

    /* 狀態色 */
    --success:     #10b981;
    --warn:        #f59e0b;
    --danger:      #ef4444;

    /* 漸層組合 */
    --grad:        linear-gradient(135deg, #7c6ff7 0%, #e879a0 100%);
    --grad-soft:   linear-gradient(135deg, rgba(124,111,247,0.15) 0%, rgba(232,121,160,0.12) 100%);
    --grad-cool:   linear-gradient(135deg, #60a5fa 0%, #7c6ff7 100%);
    --grad-green:  linear-gradient(135deg, #34d399 0%, #60a5fa 100%);
    --grad-warm:   linear-gradient(135deg, #fb923c 0%, #e879a0 100%);
    --grad-sidebar:linear-gradient(180deg, #fdfcff 0%, #f5f0ff 100%);

    /* 形狀 / 陰影 */
    --radius:      14px;
    --radius-sm:   8px;
    --font:        'Nunito', sans-serif;
    --mono:        'DM Mono', monospace;
    --shadow:      0 2px 16px rgba(124,111,247,0.10);
    --shadow-md:   0 4px 24px rgba(124,111,247,0.16);
    --shadow-lg:   0 8px 40px rgba(124,111,247,0.20);
}

/* ── 全域重設 ─────────────────────────────────────────────────────── */
html, body, [class*="css"] {
    font-family: var(--font) !important;
    color: var(--text) !important;
}

/* 主背景：柔和漸層 */
.stApp {
    background: var(--bg-grad) !important;
    background-attachment: fixed !important;
}

/* 主內容區塊基礎設定 */
.main .block-container {
    padding: 1.5rem 2.5rem 6rem !important;
    max-width: 100% !important;
    width: 100% !important;
}

/* ── 側邊欄摺疊時，主畫面完全佔滿 ────────────────────────────────
   Streamlit 摺疊後 sidebar 本身變成 width:0 但父層 flex 容器
   仍保留空間，需對以下三個層級一起處理                          */

/* 1. sidebar 摺疊後自身寬度歸零、不佔空間 */
[data-testid="stSidebar"][aria-expanded="false"] {
    width: 0 !important;
    min-width: 0 !important;
    flex: 0 0 0 !important;
    overflow: hidden !important;
}

/* 2. sidebar 內的展開箭頭按鈕移到最左側即可，不影響主內容 */
[data-testid="stSidebar"][aria-expanded="false"] > div:first-child {
    width: 0 !important;
    padding: 0 !important;
}

/* 3. 主內容區塊清除左側所有偏移 */
[data-testid="stSidebar"][aria-expanded="false"] ~ section[data-testid="stMain"],
[data-testid="stSidebar"][aria-expanded="false"] ~ .main {
    margin-left: 0 !important;
    padding-left: 0 !important;
    width: 100% !important;
    flex: 1 1 100% !important;
}
[data-testid="stSidebar"][aria-expanded="false"] ~ section[data-testid="stMain"] .block-container,
[data-testid="stSidebar"][aria-expanded="false"] ~ .main .block-container {
    padding-left: 2.5rem !important;
    padding-right: 2.5rem !important;
    max-width: 100% !important;
    width: 100% !important;
}

/* ── 隱藏 Streamlit MPA 原生頁面導覽列 ──────────────────────────── */
/* 左側 pages/ 自動產生的頁面清單 */
[data-testid="stSidebarNav"] { display: none !important; }
/* 有時包在這個容器裡 */
[data-testid="stSidebarNavItems"] { display: none !important; }
/* 分隔線也一併隱藏 */
[data-testid="stSidebarNavSeparator"] { display: none !important; }

/* ── 頂端 Header Toolbar 透明化 ─────────────────────────────────── */
/* 白色 header 背景 → 透明，融入頁面漸層 */
[data-testid="stHeader"] {
    background: rgba(245,243,255,0.75) !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
    border-bottom: 1px solid rgba(124,111,247,0.10) !important;
}
/* Deploy 按鈕與選單圖示維持可見但降低存在感 */
[data-testid="stToolbar"] {
    background: transparent !important;
}
/* 右上角 "Deploy" 按鈕 */
[data-testid="stAppDeployButton"] {
    opacity: 0.55 !important;
    transition: opacity 0.2s !important;
}
[data-testid="stAppDeployButton"]:hover {
    opacity: 1 !important;
}
/* 右上角三點選單 */
[data-testid="stMainMenu"] button {
    color: #8b85a8 !important;
    background: transparent !important;
}
/* 頂端整條 toolbar 高度避免擠壓內容 */
header[data-testid="stHeader"] {
    height: 3rem !important;
}

/* ── Sidebar ──────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: var(--grad-sidebar) !important;
    border-right: 1px solid var(--border) !important;
    min-width: 260px !important;
    box-shadow: 2px 0 16px rgba(124,111,247,0.06) !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding: 0 !important;
}

/* ── Sidebar 品牌區塊 ────────────────────────────────────────────── */
.sb-brand {
    padding: 1.4rem 1.2rem 1rem;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 10px;
    background: linear-gradient(135deg, rgba(124,111,247,0.06) 0%, rgba(232,121,160,0.04) 100%);
}
.sb-brand-icon { font-size: 1.6rem; }
.sb-brand-text {
    font-size: 1.1rem;
    font-weight: 800;
    background: var(--grad);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.01em;
}
.sb-brand-sub {
    font-size: 0.62rem;
    color: var(--text-muted);
    font-family: var(--mono);
    letter-spacing: 0.06em;
    margin-top: 2px;
}

/* ── User Chip ───────────────────────────────────────────────────── */
.sb-user-chip {
    display: flex;
    align-items: center;
    gap: 8px;
    background: rgba(124,111,247,0.07);
    border: 1px solid rgba(124,111,247,0.18);
    border-radius: 999px;
    padding: 6px 12px 6px 8px;
    margin: 0.8rem 1.2rem;
}
.sb-user-avatar {
    width: 26px; height: 26px;
    border-radius: 50%;
    background: var(--grad);
    display: flex; align-items: center; justify-content: center;
    font-size: 0.7rem; font-weight: 800; color: #fff;
    box-shadow: 0 2px 8px rgba(124,111,247,0.30);
}
.sb-user-name {
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--text);
}

/* ── Sidebar 其他 class ──────────────────────────────────────────── */
.sb-nav-wrap { padding: 0.8rem 1rem; }
.sb-nav-title {
    font-size: 0.58rem;
    font-family: var(--mono);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    padding: 0 4px;
    margin-bottom: 8px;
}
.sb-divider {
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(124,111,247,0.20), transparent);
    margin: 0.8rem 1rem;
}
.sb-params-wrap { padding: 0 1rem 1rem; flex: 1; overflow-y: auto; }
.sb-params-title {
    font-size: 0.58rem;
    font-family: var(--mono);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    padding: 0 4px;
    margin-bottom: 10px;
    display: flex; align-items: center; gap: 6px;
}
.sb-params-title::before {
    content: '';
    display: inline-block;
    width: 6px; height: 6px;
    border-radius: 50%;
    background: var(--grad);
}

/* ── 頁面標題 Hero 橫幅 ──────────────────────────────────────────── */
.page-hero {
    background: linear-gradient(135deg,
        rgba(124,111,247,0.10) 0%,
        rgba(232,121,160,0.08) 60%,
        rgba(250,245,255,0.95) 100%);
    border: 1px solid rgba(124,111,247,0.18);
    border-radius: var(--radius);
    padding: 1.6rem 2rem;
    margin-bottom: 1.8rem;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow);
}
.page-hero::before {
    content: '';
    position: absolute;
    top: -50px; right: -50px;
    width: 200px; height: 200px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(232,121,160,0.14) 0%, transparent 70%);
}
.page-hero::after {
    content: '';
    position: absolute;
    bottom: -30px; left: 30px;
    width: 120px; height: 120px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(124,111,247,0.10) 0%, transparent 70%);
}
.page-hero-icon { font-size: 2.2rem; margin-bottom: 0.4rem; position: relative; z-index: 1; }
.page-hero-title {
    font-size: 1.8rem;
    font-weight: 800;
    background: var(--grad);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 0 0.25rem;
    letter-spacing: -0.02em;
    position: relative; z-index: 1;
}
.page-hero-sub {
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: 0;
    position: relative; z-index: 1;
}

/* ── Footer ───────────────────────────────────────────────────────── */
.app-footer {
    position: fixed;
    bottom: 0; left: 0; right: 0;
    height: 36px;
    background: rgba(250,248,255,0.90);
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    border-top: 1px solid rgba(124,111,247,0.14);
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 2rem;
    z-index: 9999;
}
.footer-left {
    font-size: 0.65rem;
    font-family: var(--mono);
    color: var(--text-muted);
    display: flex; align-items: center; gap: 8px;
}
.footer-dot {
    width: 4px; height: 4px;
    border-radius: 50%;
    background: var(--grad);
    opacity: 0.7;
}
.footer-right {
    font-size: 0.65rem;
    font-family: var(--mono);
    color: var(--text-muted);
}
.footer-badge {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: rgba(124,111,247,0.08);
    border: 1px solid rgba(124,111,247,0.18);
    border-radius: 4px;
    padding: 1px 7px;
    font-size: 0.6rem;
    color: var(--accent);
}

/* ── Streamlit 元件覆寫（主內容區按鈕）──────────────────────────── */
div[data-testid="stButton"] > button {
    background: #ffffff !important;
    color: #3b3552 !important;
    border: 1px solid rgba(124,111,247,0.22) !important;
    border-radius: var(--radius-sm) !important;
    font-family: var(--font) !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 6px rgba(124,111,247,0.08) !important;
    transition: all 0.2s !important;
}
div[data-testid="stButton"] > button:hover {
    background: rgba(124,111,247,0.06) !important;
    border-color: rgba(124,111,247,0.45) !important;
    color: #7c6ff7 !important;
    box-shadow: 0 4px 14px rgba(124,111,247,0.14) !important;
}

/* ── Sidebar 導覽按鈕（type=primary）─────────────────────────────── */
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
    background: rgba(255,255,255,0.70) !important;
    border: 1px solid rgba(124,111,247,0.14) !important;
    border-radius: 10px !important;
    padding: 10px 4px !important;
    min-height: 62px !important;
    white-space: pre-wrap !important;
    line-height: 1.4 !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    color: #8b85a8 !important;
    display: flex !important;
    flex-direction: column !important;
    align-items: center !important;
    gap: 2px !important;
    box-shadow: 0 1px 4px rgba(124,111,247,0.06) !important;
    transition: all 0.2s !important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-primary"]:hover {
    background: rgba(124,111,247,0.08) !important;
    border-color: rgba(124,111,247,0.30) !important;
    color: #7c6ff7 !important;
    box-shadow: 0 3px 12px rgba(124,111,247,0.12) !important;
}

/* ── 登出按鈕（type=secondary，與 user chip 同色系）────────────────── */
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {
    background: rgba(124,111,247,0.07) !important;
    border: 1px solid rgba(124,111,247,0.20) !important;
    border-radius: 999px !important;
    color: #7c6ff7 !important;
    min-height: 36px !important;
    height: 36px !important;
    font-size: 0.8rem !important;
    font-weight: 700 !important;
    font-family: 'Nunito', sans-serif !important;
    padding: 0 16px !important;
    box-shadow: none !important;
    flex-direction: row !important;
    white-space: nowrap !important;
    letter-spacing: 0.02em !important;
    transition: all 0.2s !important;
}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {
    background: rgba(239,68,68,0.07) !important;
    border-color: rgba(239,68,68,0.28) !important;
    color: #ef4444 !important;
}

/* ── 表單元件 ────────────────────────────────────────────────────── */
[data-testid="stSelectbox"] > div > div,
[data-testid="stTextInput"] > div > div input,
[data-testid="stNumberInput"] > div > div input,
textarea {
    background: #ffffff !important;
    border: 1px solid rgba(124,111,247,0.20) !important;
    color: #3b3552 !important;
    border-radius: var(--radius-sm) !important;
    font-family: var(--font) !important;
}
[data-testid="stSelectbox"] > div > div:focus-within,
[data-testid="stTextInput"] > div > div:focus-within input {
    border-color: rgba(124,111,247,0.50) !important;
    box-shadow: 0 0 0 3px rgba(124,111,247,0.10) !important;
}

/* slider track */
[data-testid="stSlider"] [data-baseweb="slider"] [data-testid="stTickBar"] { }
[data-testid="stSlider"] div[role="slider"] {
    background: var(--grad) !important;
    border: none !important;
}

/* label */
label, .stCheckbox label, .stRadio label,
[data-testid="stWidgetLabel"] p {
    color: #5c5580 !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
}

/* ── Metric 卡片 ──────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #ffffff !important;
    border: 1px solid rgba(124,111,247,0.14) !important;
    border-radius: var(--radius) !important;
    padding: 1rem 1.2rem !important;
    box-shadow: var(--shadow) !important;
}
[data-testid="stMetricValue"] {
    color: #3b3552 !important;
    font-family: var(--font) !important;
    font-weight: 800 !important;
}
[data-testid="stMetricLabel"] p { color: #8b85a8 !important; }
[data-testid="stMetricDelta"] { font-size: 0.75rem !important; }

/* ── Expander ────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: #ffffff !important;
    border: 1px solid rgba(124,111,247,0.14) !important;
    border-radius: var(--radius) !important;
    box-shadow: var(--shadow) !important;
}

/* ── 其他 ────────────────────────────────────────────────────────── */
.stDivider { border-color: rgba(124,111,247,0.12) !important; }
h1, h2, h3, h4, h5, h6 {
    color: #3b3552 !important;
    font-family: var(--font) !important;
    font-weight: 700 !important;
}
p, li { color: #3b3552 !important; }
[data-testid="stMarkdownContainer"] p { color: #3b3552 !important; }
</style>
"""


# ══════════════════════════════════════════════════════════════════════════════
#  Session 恢復（URL query param 保留 sid）
# ══════════════════════════════════════════════════════════════════════════════

if "logged_in" not in st.session_state:
    sid = st.query_params.get("sid", "")
    username = verify_session(sid) if sid else None
    if username:
        logger.info("Session 恢復成功 ─ user=%s  sid=%s", username, sid[:8] + "…")
        st.session_state.update(logged_in=True, username=username, sid=sid)
    else:
        st.session_state.update(logged_in=False, username="", sid="")

if "active_page" not in st.session_state:
    st.session_state.active_page = "home"

# ══════════════════════════════════════════════════════════════════════════════
#  QR Code 確認路由（手機掃描後進入此頁）
# ══════════════════════════════════════════════════════════════════════════════
_qr_confirm_token: str = st.query_params.get("qr_confirm", "")

if _qr_confirm_token and not st.session_state.get("logged_in"):
    if not st.session_state.get("qr_mobile_confirmed"):

        _, col, _ = st.columns([1, 2, 1])
        with col:
            st.markdown(
                "<style>"
                "#MainMenu,footer,header,[data-testid='stToolbar']{display:none!important}"
                "</style>",
                unsafe_allow_html=True,
            )
            st.markdown(
                '<div style="text-align:center;padding:1.5rem 0 1rem;">'
                '<div style="font-size:2rem">📱</div>'
                '<div style="font-size:1.2rem;font-weight:800;color:#3b3552">QR Code 登入確認</div>'
                '<div style="font-size:.85rem;color:#8b85a8;margin-top:.3rem">'
                '請輸入您的帳號，系統將自動驗證此設備</div>'
                '</div>',
                unsafe_allow_html=True,
            )

            # ── 從 HTTP headers 收集設備指紋（伺服器端，無 JS 時序問題）──
            _headers = st.context.headers
            _ua    = _headers.get("User-Agent", "")
            _lang  = _headers.get("Accept-Language", "")
            _fp_raw = f"{_ua}|{_lang}"

            _qr_username: str = st.text_input(
                "帳號",
                placeholder="請輸入您的登入帳號",
                key="qr_device_username",
            )

            if st.button(
                "✅ 驗證並登入",
                use_container_width=True,
                type="primary",
                key="qr_device_confirm_btn",
            ):
                from core.users import user_exists
                from core.device_auth import compute_device_hash, verify_device
                from core.qr_store import confirm_qr_token

                _uname = _qr_username.strip()

                if not _uname:
                    st.error("❌ 請輸入帳號後再確認。")

                elif not user_exists(_uname):
                    logger.warning("QR 設備登入失敗 ─ 使用者不存在  user=%s", _uname)
                    st.error(f"❌ 帳號「{_uname}」不存在，請確認後重試。")

                elif not _fp_raw or len(_fp_raw) < 10:
                    # UA 完全空白才觸發（極罕見）
                    logger.warning("QR 設備登入失敗 ─ 無法取得 UA  user=%s", _uname)
                    st.error("❌ 無法識別此設備，請確認瀏覽器未封鎖 User-Agent。")

                else:
                    _device_hash = compute_device_hash(_fp_raw)

                    if not verify_device(_uname, _device_hash):
                        logger.warning(
                            "QR 設備登入失敗 ─ 設備未綁定  user=%s  hash=%s…",
                            _uname, _device_hash[:8],
                        )
                        st.error(
                            "❌ 此設備尚未綁定至您的帳號，"
                            "請先以帳號密碼登入後至「設定 → 設備管理」完成綁定。"
                        )
                    else:
                        if confirm_qr_token(_qr_confirm_token, _uname, _device_hash):
                            st.session_state.qr_mobile_confirmed = True
                            st.session_state.qr_mobile_user = _uname
                            logger.info(
                                "QR 設備登入確認成功 ─ user=%s  token=%s",
                                _uname, _qr_confirm_token[:8] + "…",
                            )
                            st.rerun()
                        else:
                            st.error("❌ Token 無效或已過期，請重新掃描 QR Code。")
        # ── 已確認：成功畫面 + 倒數自動關閉 ─────────────────────────────
    else:
        _confirmed_user: str = st.session_state.get("qr_mobile_user", "使用者")
        st.session_state.pop("qr_mobile_confirmed", None)
        st.session_state.pop("qr_mobile_user", None)

        _success_html: str = f"""<!DOCTYPE html>
        <html lang="zh-Hant">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width,initial-scale=1">
        <style>
        *{{margin:0;padding:0;box-sizing:border-box}}
        body{{
            font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
            background:linear-gradient(145deg,#f0f4ff 0%,#faf5ff 50%,#fff0f9 100%);
            padding:2rem 1rem;
            display:flex;align-items:flex-start;justify-content:center;
        }}
        .card{{
            background:#fff;border:1px solid rgba(124,111,247,.20);
            border-radius:20px;padding:2rem 1.8rem 1.8rem;
            max-width:320px;width:100%;
            box-shadow:0 8px 40px rgba(124,111,247,.14);text-align:center;
        }}
        .check{{
            width:64px;height:64px;border-radius:50%;
            background:linear-gradient(135deg,#10b981,#059669);
            display:flex;align-items:center;justify-content:center;
            font-size:1.8rem;color:#fff;margin:0 auto .9rem;
            box-shadow:0 4px 20px rgba(16,185,129,.35);
            animation:pop .4s cubic-bezier(.175,.885,.32,1.275);
        }}
        @keyframes pop{{from{{transform:scale(0);opacity:0}}to{{transform:scale(1);opacity:1}}}}
        .title{{
            font-size:1.2rem;font-weight:800;
            background:linear-gradient(135deg,#7c6ff7,#e879a0);
            -webkit-background-clip:text;-webkit-text-fill-color:transparent;
            margin-bottom:.35rem;
        }}
        .sub{{font-size:.82rem;color:#8b85a8;margin-bottom:1.2rem;line-height:1.6}}
        .sub strong{{color:#5c5580}}
        .circle{{
            width:56px;height:56px;border-radius:50%;
            background:linear-gradient(135deg,#7c6ff7,#e879a0);
            display:flex;align-items:center;justify-content:center;
            font-size:1.4rem;font-weight:800;color:#fff;
            margin:0 auto .5rem;
            box-shadow:0 4px 20px rgba(124,111,247,.35);
            animation:pulse 1s ease-in-out infinite;
        }}
        @keyframes pulse{{0%,100%{{transform:scale(1)}}50%{{transform:scale(1.08)}}}}
        .label{{font-size:.78rem;color:#5c5580;font-weight:600}}
        .hint{{
            font-size:.78rem;color:#7c6ff7;font-weight:600;
            background:rgba(124,111,247,.08);border:1px solid rgba(124,111,247,.20);
            border-radius:10px;padding:8px 14px;margin-top:.9rem;
            line-height:1.6;display:none;
        }}
        </style>
        </head>
        <body>
        <div class="card">
            <div class="check">✓</div>
            <div class="title">授權成功！</div>
            <div class="sub">帳號 <strong>{_confirmed_user}</strong> 已完成驗證<br>電腦端將自動登入</div>
            <div class="circle" id="num">3</div>
            <div class="label">秒後自動關閉此頁面</div>
            <div class="hint" id="hint">✋ 請手動關閉此分頁</div>
        </div>
        <script>
        (function(){{
            var count = 3;
            var numEl  = document.getElementById('num');
            var hintEl = document.getElementById('hint');
            var timer  = setInterval(function() {{
                count--;
                if (numEl) numEl.textContent = count;
                if (count <= 0) {{
                    clearInterval(timer);
                    try {{ window.top.location.replace('about:blank'); }} catch(e1) {{
                        try {{ window.parent.location.replace('about:blank'); }} catch(e2) {{
                            try {{ window.location.replace('about:blank'); }} catch(e3) {{}}
                            hintEl.style.display = 'block';
                            if (numEl) {{
                                numEl.textContent = '✓';
                                numEl.style.animation = 'none';
                            }}
                        }}
                    }}
                }}
            }}, 1000);
        }})();
        </script>
        </body>
        </html>"""

        import streamlit.components.v1 as components
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            components.html(_success_html, height=420, scrolling=False)

        st.stop()

# ══════════════════════════════════════════════════════════════════════════════
#  登入畫面
# ══════════════════════════════════════════════════════════════════════════════

LOGIN_CSS = """
<style>
.login-logo {
    text-align: center;
    margin-bottom: 2rem;
}
.login-logo-icon {
    font-size: 3.2rem;
    display: block;
    margin-bottom: 0.6rem;
    filter: drop-shadow(0 4px 12px rgba(124,111,247,0.30));
}
.login-title {
    font-size: 2rem;
    font-weight: 800;
    background: linear-gradient(135deg, #7c6ff7 0%, #e879a0 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    text-align: center;
    letter-spacing: -0.02em;
}
.login-sub {
    font-size: 0.82rem;
    color: #8b85a8;
    text-align: center;
    margin-top: 4px;
}
.login-hint {
    text-align: center;
    font-size: 0.7rem;
    font-family: 'DM Mono', monospace;
    color: #8b85a8;
    margin-top: 1.5rem;
    background: rgba(124,111,247,0.06);
    border: 1px solid rgba(124,111,247,0.14);
    border-radius: 8px;
    padding: 8px 12px;
}
/* 登入表單送出按鈕 */
[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #7c6ff7 0%, #e879a0 100%) !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    padding: 0.65rem 1rem !important;
    box-shadow: 0 4px 20px rgba(124,111,247,0.30) !important;
    transition: opacity 0.2s, transform 0.15s !important;
}
[data-testid="stFormSubmitButton"] > button:hover {
    opacity: 0.92 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 24px rgba(124,111,247,0.40) !important;
}
</style>
"""


def _show_totp_enrollment() -> None:
    """
    首次 TOTP 設定閘門頁面。
    在使用者第一次登入成功（密碼正確）後顯示，
    強制完成 Google Authenticator 設定才可進入主程式。
    session 尚未建立，無法繞過此頁面。
    """
    from core.totp import generate_secret, generate_setup_qr_png, verify_code
    from core.users import save_totp_secret

    enrolling_user: str = st.session_state.get("totp_enrolling_user", "")
    if not enrolling_user:
        st.rerun()
        return

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        st.markdown(
            """
            <div class="login-logo">
                <span class="login-logo-icon">🛡️</span>
                <div class="login-title">安全設定</div>
                <div class="login-sub">請完成 Google 驗證器設定以繼續</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── 產生 secret（只產生一次，存 session_state）──────────
        if "totp_enroll_secret" not in st.session_state:
            st.session_state.totp_enroll_secret = generate_secret()

        secret: str = st.session_state.totp_enroll_secret

        # ── Step 1：掃描 QR ───────────────────────────────────────
        st.markdown("**Step 1** 　開啟 Google Authenticator，掃描下方 QR Code")
        qr_png = generate_setup_qr_png(secret, enrolling_user)

        col_qr, col_key = st.columns([1, 1])
        with col_qr:
            st.image(qr_png, width=180)
        with col_key:
            st.markdown("手動輸入密鑰：")
            st.code(secret, language=None)
            st.caption("⚠️ 請截圖或記錄此密鑰，遺失後無法復原。")

        st.divider()

        # ── Step 2：驗證碼確認 ────────────────────────────────────
        st.markdown("**Step 2** 　輸入 App 顯示的 6 位數驗證碼")

        with st.form("totp_enroll_form"):
            confirm_code = st.text_input(
                "驗證碼",
                max_chars=6,
                placeholder="請輸入 6 位數驗證碼",
            )
            col_submit, col_cancel = st.columns([2, 1])
            with col_submit:
                submitted = st.form_submit_button(
                    "✅ 完成設定，進入系統", use_container_width=True, type="primary"
                )
            with col_cancel:
                cancelled = st.form_submit_button("← 返回", use_container_width=True)

        if submitted:
            if verify_code(secret, confirm_code):
                # 驗證通過 → 儲存 secret，建立 session，進入 App
                if save_totp_secret(enrolling_user, secret):
                    sid = create_session(enrolling_user)
                    user_id  = get_user_id(enrolling_user)  # ← 新增
                    st.session_state.update(
                        logged_in=True,
                        username=enrolling_user,
                        sid=sid,
                        user_id=user_id,
                    )
                    # 清除 enrollment 相關 state
                    st.session_state.pop("totp_enrolling_user", None)
                    st.session_state.pop("totp_enroll_secret", None)
                    st.query_params["sid"] = sid
                    logger.info(
                        "首次 TOTP 設定完成，進入系統 ─ user=%s  sid=%s",
                        enrolling_user,
                        sid[:8] + "…",
                    )
                    log_section("MAIN APPLICATION LOADED")
                    st.rerun()
                else:
                    st.error("❌ 儲存失敗，請稍後再試。")
            else:
                st.error("❌ 驗證碼錯誤，請確認 App 時間同步後重試。")

        if cancelled:
            # 取消 → 清除所有 enrollment state，回到登入頁
            st.session_state.pop("totp_enrolling_user", None)
            st.session_state.pop("totp_enroll_secret", None)
            logger.info("使用者取消 TOTP 設定 ─ user=%s", enrolling_user)
            st.rerun()


def show_login() -> None:
    log_section("LOGIN PAGE")
    logger.info("顯示登入畫面")

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown(
            """
            <div class="login-logo">
                <span class="login-logo-icon">⚡</span>
                <div class="login-title">StProject</div>
                <div class="login-sub">Powered by Streamlit &amp; uv</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        tab_pw, tab_qr = st.tabs(["🔐 帳號密碼", "📱 QR Code 掃描登入"])

        # ── Tab 1：帳號密碼 + TOTP 登入 ──────────────────────────
        with tab_pw:
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("👤  帳號", placeholder="請輸入帳號")
                password = st.text_input(
                    "🔒  密碼", type="password", placeholder="請輸入密碼"
                )
                totp_code = st.text_input(
                    "🔐  Google 驗證碼",
                    placeholder="6 位數驗證碼（未啟用可留空）",
                    max_chars=6,
                )
                submit = st.form_submit_button("登 入", use_container_width=True)

            if submit:
                from core.users import verify_login, get_totp_info  # 確保使用新版函式

                logger.info("登入嘗試 ─ user=%s", username)
                ok, reason = verify_login(username, password, totp_code)
                if ok:
                    # ── 檢查是否已設定 TOTP ──────────────────────
                    totp_enabled, _ = get_totp_info(username)
                    if not totp_enabled:
                        # 首次使用：導向 TOTP 強制設定閘門
                        st.session_state.totp_enrolling_user = username
                        logger.info("首次 TOTP 設定引導 ─ user=%s", username)
                        st.rerun()
                    else:
                        # 已設定 TOTP → 正常建立 session
                        sid = create_session(username)
                        user_id = get_user_id(username)
                        st.session_state.update(
                            logged_in=True, username=username, sid=sid, user_id=user_id
                        )
                        st.query_params["sid"] = sid
                        logger.info(
                            "登入成功 ─ user=%s  sid=%s", username, sid[:8] + "…"
                        )
                        log_section("MAIN APPLICATION LOADED")
                        st.rerun()
                else:
                    _LOGIN_ERRORS = {
                        "wrong_password": "帳號或密碼錯誤，請重試。",
                        "totp_required": "此帳號已啟用 Google 驗證，請輸入 6 位數驗證碼。",
                        "wrong_totp": "Google 驗證碼錯誤或已過期，請重試。",
                        "not_found": "帳號不存在，請確認後重試。",
                    }
                    logger.warning("登入失敗 ─ user=%s  reason=%s", username, reason)
                    st.error(_LOGIN_ERRORS.get(reason, "登入失敗，請稍後再試。"))

            st.markdown(
                "<div class='login-hint'>測試帳號：admin / admin123 　或　 user / user123</div>",
                unsafe_allow_html=True,
            )
        # ── Tab 2：QR Code 登入 ──────────────────────────────────
        with tab_qr:
            _show_qr_login_tab()


def _show_qr_login_tab() -> None:
    """
    QR Code 登入 Tab。
    Fragment 只負責輪詢與寫入登入結果，
    外層偵測 flag 後用 scope='app' 強制整頁 rerun。
    """

    # ── Token 初始化 ─────────────────────────────────────────────
    if "qr_token_id" not in st.session_state or not st.session_state.qr_token_id:
        st.session_state.qr_token_id = create_qr_token()

    # ── ✅ 外層先檢查登入 flag（Fragment rerun 後會回到這裡）────
    if st.session_state.get("qr_login_success"):
        # 清除 flag，執行真正的整頁跳轉
        st.session_state.pop("qr_login_success", None)
        st.session_state.pop("qr_token_id", None)
        logger.info(
            "QR 登入完成，整頁跳轉 ─ user=%s",
            st.session_state.get("username"),
        )
        # scope="app" = 強制整頁 rerun，等同於使用者手動重新整理
        st.rerun(scope="app")

    # ── Fragment：只重跑此區塊，不凍結整頁 UI ───────────────────
    @st.fragment(run_every=3)
    def _qr_polling_block() -> None:
        token_id: str = st.session_state.get("qr_token_id", "")
        if not token_id:
            return

        status, confirmed_user = check_qr_token(token_id)

        # Token 過期 → 重新產生
        if status == "expired":
            st.session_state.qr_token_id = create_qr_token()
            st.warning("⏰ QR Code 已過期，正在重新產生…")
            st.rerun()  # Fragment 層級即可
            return

        # ✅ 確認成功 → 寫入 session_state，設定 flag
        if status == "confirmed" and confirmed_user:
            from core.users import get_totp_info
            totp_enabled, _ = get_totp_info(confirmed_user)
            consume_qr_token(token_id)

            if not totp_enabled:
                # QR 登入後同樣引導至 TOTP 設定閘門
                st.session_state.update(
                    totp_enrolling_user=confirmed_user,
                    qr_token_id=None,
                    qr_login_success=True,
                )
            else:
                sid = create_session(confirmed_user)
                user_id = get_user_id(confirmed_user)
                st.session_state.update(
                    logged_in=True,
                    username=confirmed_user,
                    sid=sid,
                    user_id=user_id,
                    qr_token_id=None,
                    qr_login_success=True,
                )
                st.query_params["sid"] = sid
            logger.info(
                "QR Token 確認完成，寫入 session ─ user=%s  sid=%s",
                confirmed_user,
                sid[:8] + "…",
            )

            # Fragment 層級 rerun，讓外層函式重跑並偵測到 flag
            st.rerun()

        # ── QR Code 顯示區 ───────────────────────────────────────
        from core.qr_login import generate_qr_image, build_confirm_url
        from core.network import get_local_ip

        confirm_url = build_confirm_url(token_id, port=8501)
        qr_bytes = generate_qr_image(confirm_url)
        local_ip = get_local_ip()

        # 內網 IP 提示
        st.markdown(
            f"""
            <div style='text-align:center;background:rgba(124,111,247,0.08);
                        border:1px solid rgba(124,111,247,0.2);border-radius:8px;
                        padding:6px 12px;margin-bottom:8px;font-size:0.75rem;
                        color:#5c5580;font-family:"DM Mono",monospace'>
                🌐 內網服務位址：<strong>{local_ip}:8501</strong>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # QR Code 圖片置中
        _, img_col, _ = st.columns([1, 1, 1])
        with img_col:
            st.image(qr_bytes, width=200)

        # 完整連結文字
        st.markdown(
            f"<div style='text-align:center;font-size:0.72rem;color:#8b85a8;"
            f"word-break:break-all;margin-top:0.3rem'>{confirm_url}</div>",
            unsafe_allow_html=True,
        )

        # 狀態指示
        _render_status_indicator(status)

    # 呼叫 fragment（每次外層執行都會重新掛載）
    _qr_polling_block()


def _render_status_indicator(status: str) -> None:
    """根據狀態顯示對應提示"""
    status_map: dict[str, tuple[str, str]] = {
        "pending": ("⏳", "等待掃描中… (每 3 秒自動偵測)", "#8b85a8"),
        "confirmed": ("✅", "掃描成功！正在登入…", "#10b981"),
        "expired": ("❌", "已過期，請重新整理", "#ef4444"),
    }
    icon, msg, color = status_map.get(status, ("❓", "未知狀態", "#8b85a8"))
    st.markdown(
        f"""
        <p style='text-align:center;color:{color};
                  font-size:0.82rem;margin-top:0.8rem'>
            {icon} {msg}
        </p>
        """,
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  頁面設定清單（上半部導覽 + 下半部參數面板定義）
# ══════════════════════════════════════════════════════════════════════════════

PAGE_CONFIG: list[dict[str, Any]] = [
    {
        "id": "home",
        "icon": "🏠",
        "label": "首頁",
        "title": "系統首頁",
        "subtitle": "歡迎使用 StProject 管理平台",
        "module": "pages.home",
        "params": [],  # 首頁無側邊欄參數
    },
    {
        "id": "daily_expense",
        "icon": "💰",
        "label": "消費",
        "title": "每日消費記錄",
        "subtitle": "快速記帳 · 今日總覽 · 預算追蹤",
        "module": "pages.daily_expense",
        "params": [],  # 此頁無側邊欄參數
    },
    {
        "id": "dashboard",
        "icon": "📊",
        "label": "儀表板",
        "title": "資料儀表板",
        "subtitle": "圖表分析與關鍵指標總覽",
        "module": "pages.dashboard",
        "params": [
            {
                "type": "selectbox",
                "key": "dash_range",
                "label": "時間範圍",
                "options": ["最近 7 天", "最近 30 天", "最近 90 天", "本年度"],
                "default": 0,
            },
            {
                "type": "selectbox",
                "key": "dash_chart",
                "label": "圖表類型",
                "options": ["折線圖", "長條圖", "面積圖"],
                "default": 0,
            },
            {
                "type": "checkbox",
                "key": "dash_animate",
                "label": "啟用動態效果",
                "default": True,
            },
        ],
    },
    {
        "id": "crawler",
        "icon": "🕸",
        "label": "爬蟲",
        "title": "網頁爬蟲工作台",
        "subtitle": "資料搜集、彙整分析與二階段 Pipeline",
        "module": "pages.crawler_dashboard",
        "params": [
            {
                "type": "number",
                "key": "crawl_concurrency",
                "label": "最大並發數",
                "min": 1,
                "max": 10,
                "default": 3,
            },
            {
                "type": "slider",
                "key": "crawl_delay",
                "label": "請求延遲 (秒)",
                "min": 0.5,
                "max": 5.0,
                "step": 0.5,
                "default": 1.5,
            },
            {
                "type": "number",
                "key": "crawl_timeout",
                "label": "逾時時間 (秒)",
                "min": 5,
                "max": 60,
                "default": 15,
            },
            {
                "type": "number",
                "key": "crawl_retries",
                "label": "最大重試次數",
                "min": 0,
                "max": 10,
                "default": 3,
            },
            {
                "type": "checkbox",
                "key": "crawl_robots",
                "label": "遵守 robots.txt",
                "default": True,
            },
        ],
    },
    {
        "id": "upscaler",
        "icon": "🖼",
        "label": "超解析度",
        "title": "AI 圖像超解析度",
        "subtitle": "GPU 加速 · PyTorch EDSR · 人像細節強化",
        "module": "pages.image_upscaler",
        "params": [
            {
                "type": "selectbox",
                "key": "up_model",
                "label": "AI 模型",
                "options": ["EDSR", "ESPCN", "FSRCNN", "LapSRN"],
                "default": 0,
            },
            {
                "type": "selectbox",
                "key": "up_scale",
                "label": "放大倍數",
                "options": ["2×", "3×", "4×"],
                "default": 0,
            },
            {
                "type": "checkbox",
                "key": "up_gpu",
                "label": "啟用 GPU 加速",
                "default": True,
            },
            {
                "type": "checkbox",
                "key": "up_portrait",
                "label": "人像細節強化模式",
                "default": False,
            },
            {
                "type": "slider",
                "key": "up_sharpen",
                "label": "銳化強度",
                "min": 0.0,
                "max": 3.0,
                "step": 0.1,
                "default": 1.2,
            },
        ],
    },
    {
        "id": "settings",
        "icon": "⚙️",
        "label": "設定",
        "title": "系統設定",
        "subtitle": "個人資料、密碼修改與外觀偏好",
        "module": "pages.settings",
        "params": [],
    },
]

# 建立 id → config 的快速查找字典
PAGE_MAP: dict[str, dict] = {p["id"]: p for p in PAGE_CONFIG}


# ══════════════════════════════════════════════════════════════════════════════
#  側邊欄渲染
# ══════════════════════════════════════════════════════════════════════════════

_NAV_BTN_TMPL = """
<a href="javascript:void(0);" class="nav-btn {active_cls}"
   onclick="window.parent.postMessage({{type:'streamlit:setComponentValue',value:'{pid}'}}, '*')"
   title="{label}">
  <span class="nav-btn-icon">{icon}</span>
  <span class="nav-btn-label">{label}</span>
</a>
"""


def _clear_other_page_params(current_page_id: str) -> None:
    """
    切換頁面時，把其他頁面的 params key 從 session_state 清除。
    避免殘留的型別（str/float/int）污染下一頁的 widget 初始值。
    """
    current_keys: set[str] = {
        p["key"]
        for cfg in PAGE_CONFIG
        if cfg["id"] == current_page_id
        for p in cfg.get("params", [])
    }
    other_keys: list[str] = [
        p["key"]
        for cfg in PAGE_CONFIG
        if cfg["id"] != current_page_id
        for p in cfg.get("params", [])
        if p["key"] not in current_keys  # 不同頁若剛好同名 key 則保留
    ]
    for k in other_keys:
        if k in st.session_state:
            del st.session_state[k]


def _render_params(page_cfg: dict) -> None:
    """渲染側邊欄下半部的功能參數面板，附型別安全防呆"""
    params = page_cfg.get("params", [])
    if not params:
        st.markdown(
            "<p style='font-size:0.72rem;color:#8b85a8;"
            'font-family:"DM Mono",monospace;padding:0 4px\'>'
            "此頁面無額外參數</p>",
            unsafe_allow_html=True,
        )
        return

    for p in params:
        ptype: str = p["type"]
        key: str = p["key"]
        label: str = p["label"]

        if ptype == "selectbox":
            options: list = p["options"]
            default_val: str = options[p["default"]]
            current = st.session_state.get(key, default_val)
            # 強制轉為合法索引
            if isinstance(current, str) and current in options:
                idx = options.index(current)
            elif isinstance(current, int) and 0 <= current < len(options):
                idx = current
            else:
                idx = p["default"]
            st.selectbox(label, options, index=idx, key=key)

        elif ptype == "checkbox":
            default_bool: bool = bool(p["default"])
            current = st.session_state.get(key, default_bool)
            # 強制為 bool
            safe_val = bool(current) if not isinstance(current, bool) else current
            if key in st.session_state and not isinstance(st.session_state[key], bool):
                del st.session_state[key]
            st.checkbox(label, value=safe_val, key=key)

        elif ptype == "slider":
            lo, hi, step = float(p["min"]), float(p["max"]), float(p["step"])
            default_f = float(p["default"])
            current = st.session_state.get(key, default_f)
            try:
                safe_val = float(current)
                safe_val = max(lo, min(hi, safe_val))
            except (TypeError, ValueError):
                safe_val = default_f
            if key in st.session_state and not isinstance(st.session_state[key], float):
                del st.session_state[key]
            st.slider(
                label, min_value=lo, max_value=hi, step=step, value=safe_val, key=key
            )

        elif ptype == "number":
            lo_i, hi_i = int(p["min"]), int(p["max"])
            default_i = int(p["default"])
            current = st.session_state.get(key, default_i)
            try:
                safe_val = int(current)
                safe_val = max(lo_i, min(hi_i, safe_val))
            except (TypeError, ValueError):
                safe_val = default_i
            if key in st.session_state and not isinstance(st.session_state[key], int):
                del st.session_state[key]
            st.number_input(
                label, min_value=lo_i, max_value=hi_i, value=safe_val, step=1, key=key
            )


def render_sidebar(active_id: str) -> str:
    """渲染完整側邊欄，回傳可能被選取的新頁面 id"""
    new_page = active_id

    with st.sidebar:
        # ── Brand ──────────────────────────────────────────────────
        st.markdown(
            f"""
            <div class="sb-brand">
                <span class="sb-brand-icon">⚡</span>
                <div>
                    <div class="sb-brand-text">StProject</div>
                    <div class="sb-brand-sub">v1.0.0 · uv workspace</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── User chip（一列）──────────────────────────────────────
        uname = st.session_state.get("username", "?")
        initial = uname[0].upper() if uname else "?"

        st.markdown(
            f"""
            <div class="sb-user-chip">
                <div class="sb-user-avatar">{initial}</div>
                <span class="sb-user-name">{uname}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── 登出按鈕（下一列，secondary type，CSS 精確定位）─────────
        if logout_clicked := st.button(
            "🚪  登出", key="logout_btn", use_container_width=True
        ):
            logger.info("使用者登出 ─ user=%s", st.session_state.get("username"))
            delete_session(st.session_state.sid)
            st.session_state.update(logged_in=False, username="", sid="")
            st.query_params.clear()
            log_section("SESSION ENDED")
            st.rerun()

        # ── 導覽按鈕（上半部）─────────────────────────────────────
        st.markdown(
            '<p style=\'font-size:0.58rem;font-family:"JetBrains Mono",monospace;'
            "color:#8890a4;text-transform:uppercase;letter-spacing:0.12em;"
            "padding:0 4px;margin:0.6rem 0 0.5rem'>▪ 功能導覽</p>",
            unsafe_allow_html=True,
        )

        # 每列最多 3 個按鈕，以 st.columns 實現
        for row_start in range(0, len(PAGE_CONFIG), 3):
            row_pages = PAGE_CONFIG[row_start : row_start + 3]
            cols = st.columns(len(row_pages))
            for col, page in zip(cols, row_pages):
                with col:
                    if st.button(
                        f"{page['icon']}\n{page['label']}",
                        key=f"nav_{page['id']}",
                        use_container_width=True,
                        help=page["title"],
                        type="primary",
                    ):
                        new_page = page["id"]
                        logger.info(
                            "導覽切換 ─ %s → %s  (user=%s)",
                            active_id,
                            page["id"],
                            st.session_state.get("username"),
                        )

        # ── 分隔線 ──────────────────────────────────────────────────
        st.markdown("<div class='sb-divider'></div>", unsafe_allow_html=True)

        # ── 功能參數（下半部）────────────────────────────────────────
        active_cfg = PAGE_MAP.get(active_id, PAGE_CONFIG[0])

        # 清除其他頁面殘留的 session_state，防止型別污染
        _clear_other_page_params(active_id)

        st.markdown(
            f"<div class='sb-params-title'>⚙  {active_cfg['label']} 設定參數</div>",
            unsafe_allow_html=True,
        )
        _render_params(active_cfg)

    return new_page


# ══════════════════════════════════════════════════════════════════════════════
#  頁面標題橫幅 + Footer
# ══════════════════════════════════════════════════════════════════════════════


def render_page_hero(page_cfg: dict) -> None:
    """渲染頁面最上方的標題橫幅"""
    st.markdown(
        f"""
        <div class="page-hero">
            <div class="page-hero-icon">{page_cfg['icon']}</div>
            <div class="page-hero-title">{page_cfg['title']}</div>
            <p class="page-hero-sub">{page_cfg['subtitle']}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _inject_active_nav_style(active_id: str) -> None:
    """
    注入 active 導覽按鈕高亮樣式。
    Streamlit button 的 DOM key 不直接暴露於 CSS selector，
    改用 sidebar 內所有 stButton 的順序（nth-of-type）精確定位。
    PAGE_CONFIG 的順序即為按鈕的渲染順序。
    """
    active_idx = next(
        (i + 1 for i, p in enumerate(PAGE_CONFIG) if p["id"] == active_id), 1
    )
    st.markdown(
        f"""
        <style>
        /* Active nav button: 側邊欄第 {active_idx} 個 primary button */
        [data-testid="stSidebar"] [data-testid="stButton"]:nth-of-type({active_idx}) [data-testid="stBaseButton-primary"] {{
            background: linear-gradient(135deg,
                rgba(124,111,247,0.16) 0%,
                rgba(232,121,160,0.12) 100%) !important;
            border: 1px solid rgba(124,111,247,0.40) !important;
            color: #7c6ff7 !important;
            box-shadow: 0 2px 12px rgba(124,111,247,0.16),
                        inset 0 1px 0 rgba(255,255,255,0.60) !important;
            font-weight: 700 !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    """渲染畫面底部固定 Footer"""
    today = datetime.date.today().strftime("%Y-%m-%d")
    st.markdown(
        f"""
        <div class="app-footer">
            <div class="footer-left">
                <span class="footer-dot"></span>
                <span>Designed by <strong style="color:var(--accent)">Bllln</strong></span>
                <span class="footer-dot"></span>
                <span>StProject © 2026</span>
            </div>
            <div class="footer-right">
                <span class="footer-badge">📅 {today}</span>
                &nbsp;
                <span class="footer-badge">⚡ Streamlit + uv</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  主畫面路由
# ══════════════════════════════════════════════════════════════════════════════


def show_main() -> None:
    # 注入全域 CSS
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    # 渲染側邊欄，取回可能的新頁面選擇
    new_page = render_sidebar(st.session_state.active_page)

    # 注入 active 導覽按鈕高亮（在 sidebar 渲染後）
    _inject_active_nav_style(st.session_state.active_page)

    # 偵測頁面切換
    if new_page != st.session_state.active_page:
        st.session_state.active_page = new_page
        st.rerun()

    active_id = st.session_state.active_page
    page_cfg = PAGE_MAP.get(active_id, PAGE_CONFIG[0])

    # ── 頁面 Hero 標題 ────────────────────────────────────────────
    render_page_hero(page_cfg)

    # ── Log 頁面進入 ──────────────────────────────────────────────
    log_section(f"PAGE: {page_cfg['title'].upper()}")
    logger.info(
        "進入功能頁面 ─ id=%s  title=%s  user=%s",
        active_id,
        page_cfg["title"],
        st.session_state.get("username"),
    )

    # ── 動態載入頁面模組 ──────────────────────────────────────────
    module_path = page_cfg["module"]
    try:
        import importlib

        mod = importlib.import_module(module_path)
        if hasattr(mod, "show"):
            mod.show()
        elif hasattr(mod, "main"):
            mod.main()
        else:
            st.warning(f"⚠️ 模組 `{module_path}` 尚未實作 `show()` 函式。")
            logger.warning("模組缺少 show() ─ module=%s", module_path)
    except ModuleNotFoundError as exc:
        st.error(f"❌ 無法載入模組：`{module_path}`\n\n{exc}")
        logger.error("模組載入失敗 ─ module=%s  error=%s", module_path, exc)
    except Exception as exc:
        st.error(f"❌ 頁面執行發生錯誤：{exc}")
        logger.exception("頁面執行例外 ─ module=%s", module_path)

    # ── Footer（固定在畫面底部）───────────────────────────────────
    render_footer()


# ══════════════════════════════════════════════════════════════════════════════
#  程式進入點
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.get("totp_enrolling_user"):
    # 密碼已驗證，但尚未設定 TOTP → 顯示設定閘門
    _show_totp_enrollment()

elif st.session_state.logged_in:
    # 正常已登入 → 進入主程式
    show_main()

else:
    # 未登入 → 顯示登入頁
    show_login()
