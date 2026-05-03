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

from config.pages import PAGE_CONFIG, PAGE_MAP

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
    page_title="Bllln Web",
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
div[data-testid="stSidebarUserContent"] {
    margin:0px 0.2rem !important;
}
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
    font-size: 1.5rem;
    font-weight: 800;
    background: var(--grad);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    letter-spacing: -0.01em;
}
.sb-brand-sub {
    font-size: 0.8rem;
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
    margin: 1.2rem 1.2rem;
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
    font-size: 1rem;
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
#  側邊欄導覽靜態樣式（Static Sidebar Nav CSS）
#  ▸ 不含任何動態資訊（無 active_id、無 row/col 計算）
#  ▸ 與 GLOBAL_CSS 同層級，在 show_main() 每次 re-run 時穩定注入
#  ▸ _inject_sidebar_nav_style() 只負責注入 active 選擇器 + overflow JS
# ══════════════════════════════════════════════════════════════════════════════

_SB = '[data-testid="stSidebar"]'
_HB = '[data-testid="stHorizontalBlock"]'
_COL = '[data-testid="stColumn"]'
_BTN = 'button[data-testid="stBaseButton-secondary"]'
_NAV_ALL = f"{_SB} {_HB}:not(:first-of-type) {_BTN}"
_NAV_LOGOUT = f"{_SB} {_HB}:first-of-type {_BTN}"

SIDEBAR_NAV_CSS: str = f"""
<style>
/* ── 排版與外觀（不含 box-shadow / transition，交由 JS 的 inline !important 處理）── */
{_NAV_ALL} {{
    background      : linear-gradient(160deg,
                        #e6fdf6 0%, #f2faff 50%, #edf5ff 100%) !important;
    border          : 1.5px solid rgba(29,158,117,0.28) !important;
    border-radius   : 10px !important;
    padding         : 10px 4px !important;
    min-height      : 62px !important;
    width           : 100% !important;
    white-space     : pre-wrap !important;
    line-height     : 1.4 !important;
    font-size       : 0.75rem !important;
    font-weight     : 600 !important;
    color           : #0f6e56 !important;
    display         : flex !important;
    flex-direction  : column !important;
    align-items     : center !important;
    justify-content : center !important;
    gap             : 3px !important;
    position        : relative !important;
    cursor          : pointer !important;
}}

/* ── 登出按鈕排版 ── */
{_NAV_LOGOUT} {{
    background    : rgba(124,111,247,0.07) !important;
    border        : 1px solid rgba(124,111,247,0.20) !important;
    border-radius : 15px !important;
    color         : #7c6ff7 !important;
    min-height    : 36px !important;
    height        : 50px !important;
    font-size     : 0.8rem !important;
    font-weight   : 700 !important;
    padding       : 0 16px !important;
    flex-direction: row !important;
    white-space   : nowrap !important;
}}
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
                "請輸入您的帳號，系統將自動驗證此設備</div>"
                "</div>",
                unsafe_allow_html=True,
            )

            # ── 從 HTTP headers 收集設備指紋（伺服器端，無 JS 時序問題）──
            _headers = st.context.headers
            _ua = _headers.get("User-Agent", "")
            _lang = _headers.get("Accept-Language", "")
            _fp_raw = f"{_ua}|{_lang}"

            _qr_username: str = st.text_input(
                "帳號",
                placeholder="請輸入您的登入帳號",
                key="qr_device_username",
            )

            if st.button(
                "✅ 驗證並登入",
                width='stretch',
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
                            _uname,
                            _device_hash[:8],
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
                                _uname,
                                _qr_confirm_token[:8] + "…",
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
            height:420px;overflow:hidden;
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
                    /* st.html() 直接在主頁面執行，window 即分頁本身 */
                    /* OAuth flow 由 window.open() 開啟的分頁，window.close() 可直接關閉 */
                    var closed = false;
                    try {{
                        window.close();
                        /* 給瀏覽器 300ms 執行關閉，若分頁仍存在則 fallback */
                        setTimeout(function() {{
                            if (!closed) {{
                                try {{
                                    window.location.replace('about:blank');
                                }} catch(e) {{
                                    if (hintEl) hintEl.style.display = 'block';
                                }}
                                if (numEl) {{
                                    numEl.textContent = '✓';
                                    numEl.style.animation = 'none';
                                }}
                            }}
                        }}, 300);
                    }} catch(e) {{
                        if (hintEl) hintEl.style.display = 'block';
                        if (numEl) {{
                            numEl.textContent = '✓';
                            numEl.style.animation = 'none';
                        }}
                    }}
                }}
            }}, 1000);
        }})();
        </script>
        </body>
        </html>"""


        # ✅ 新 API，一行搞定，警告徹底消失
        st.html(_success_html, unsafe_allow_javascript=True)

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
                    "✅ 完成設定，進入系統", width='stretch', type="primary"
                )
            with col_cancel:
                cancelled = st.form_submit_button("← 返回", width='stretch')

        if submitted:
            if verify_code(secret, confirm_code):
                # 驗證通過 → 儲存 secret，建立 session，進入 App
                if save_totp_secret(enrolling_user, secret):
                    sid = create_session(enrolling_user)
                    user_id = get_user_id(enrolling_user)  # ← 新增
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


def _render_login_tab_bar() -> None:
    """
    自訂登入頁 Tab Bar。
    用 session_state 追蹤當前 tab，點擊時觸發 rerun 切換內容。
    """
    # 注入 Tab Bar CSS（只需注入一次，寫在 LOGIN_CSS 裡也可以）
    st.markdown(
        """
        <style>
        div[data-testid="stHorizontalBlock"]:has(.login-tab-btn) {
            gap: 0 !important;
        }
        .login-tab-btn button {
            border: none !important;
            border-bottom: 3px solid transparent !important;
            border-radius: 0 !important;
            background: transparent !important;
            color: #8b85a8 !important;
            font-size: 0.88rem !important;
            font-weight: 600 !important;
            padding: 6px 0 8px !important;
            width: 100% !important;
            transition: color .2s, border-color .2s !important;
        }
        .login-tab-btn button:hover {
            color: #7c6ff7 !important;
            border-bottom-color: rgba(124,111,247,.35) !important;
        }
        .login-tab-active button {
            color: #7c6ff7 !important;
            border-bottom-color: #7c6ff7 !important;
        }
        .login-tab-divider {
            border: none;
            border-top: 1px solid rgba(124,111,247,.15);
            margin: 0 0 1.2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    active = st.session_state.active_login_tab
    col_pw, col_qr = st.columns(2)

    with col_pw:
        # active tab 用 class 標記，非 active 才需要點擊切換
        css_class = (
            "login-tab-btn login-tab-active"
            if active == "password"
            else "login-tab-btn"
        )
        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
        if st.button("🔐 帳號密碼", key="tab_btn_pw", use_container_width=True):
            if active != "password":
                # 離開 QR tab → 清除 token，停止無效輪詢
                st.session_state.pop("qr_token_id", None)
                st.session_state.active_login_tab = "password"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with col_qr:
        css_class = (
            "login-tab-btn login-tab-active" if active == "qr" else "login-tab-btn"
        )
        st.markdown(f'<div class="{css_class}">', unsafe_allow_html=True)
        if st.button("📱 QR Code 掃描登入", key="tab_btn_qr", use_container_width=True):
            if active != "qr":
                st.session_state.active_login_tab = "qr"
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr class='login-tab-divider'>", unsafe_allow_html=True)


def show_login() -> None:
    log_section("LOGIN PAGE")
    logger.info("顯示登入畫面")

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

    if "active_login_tab" not in st.session_state:
        st.session_state.active_login_tab = "password"
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown(
            """
            <div class="login-logo">
                <span class="login-logo-icon">⚡</span>
                <div class="login-title">Bllln Web</div>
                <div class="login-sub">Powered by Streamlit &amp; uv</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── 自訂 Tab Bar ─────────────────────────────────────────
        _render_login_tab_bar()

        # ── Tab 1：帳號密碼 + TOTP 登入 ──────────────────────────
        if st.session_state.active_login_tab == "password":
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
                from core.users import verify_login, get_totp_info

                logger.info("登入嘗試 ─ user=%s", username)
                ok, reason = verify_login(username, password, totp_code)
                if ok:
                    totp_enabled, _ = get_totp_info(username)
                    if not totp_enabled:
                        st.session_state.totp_enrolling_user = username
                        logger.info("首次 TOTP 設定引導 ─ user=%s", username)
                        st.rerun()
                    else:
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

        # ── Tab 2：QR Code 登入（只有選中時才掛載）────────────────
        elif st.session_state.active_login_tab == "qr":
            _show_qr_login_tab()  # fragment 在此才被建立，run_every 才開始計時


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
                    <div class="sb-brand-text">Bllln Web</div>
                    <div class="sb-brand-sub">v1.0.0 · uv workspace</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        side_user, side_logout = st.sidebar.columns(
            [5, 2], gap="xxsmall", vertical_alignment="bottom"
        )

        # ── User chip（一列）──────────────────────────────────────
        uname = st.session_state.get("username", "?")
        initial = uname[0].upper() if uname else "?"

        side_user.markdown(
            f"""
            <div class="sb-user-chip">
                <div class="sb-user-avatar">{initial}</div>
                <span class="sb-user-name">{uname}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── 登出按鈕（下一列，secondary type，CSS 精確定位）─────────
        if logout_clicked := side_logout.button(
            "🚪  登出", key="logout_btn", width='stretch'
        ):
            logger.info("使用者登出 ─ user=%s", st.session_state.get("username"))
            delete_session(st.session_state.sid)
            st.session_state.update(logged_in=False, username="", sid="")
            st.query_params.clear()
            log_section("SESSION ENDED")
            st.rerun()

        # ── 導覽按鈕（上半部）─────────────────────────────────────
        st.markdown(
            '<p style=\'font-size:1rem;font-family:"JetBrains Mono",monospace;'
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
                        width='stretch',
                        help=page["title"],
                        type="secondary",  # ← secondary，避開 primaryColor 鎖定
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


def _inject_sidebar_nav_style(active_id: str) -> None:
    """
    【架構說明】
    CSS (st.markdown)  → 排版 / 背景 / 邊框（SIDEBAR_NAV_CSS 常數）
    CSS (st.markdown)  → active 按鈕高亮（此函式動態注入）
    JS  (st.iframe)    → box-shadow 3D + transition + hover 動效
                         全部用 setProperty('...','...','important')
                         inline !important > 任何 stylesheet !important
                         切頁後 React 若保留同一 DOM 節點，inline style 不消失
                         若 React 替換節點，MutationObserver 重新套用
    """
    active_idx: int = next(
        (i for i, p in enumerate(PAGE_CONFIG) if p["id"] == active_id), 0
    )
    row_block: int = (active_idx // 3) + 2
    col_pos:   int = (active_idx % 3) + 1

    _active = (
        f'{_SB} {_HB}:nth-of-type({row_block}) '
        f'{_COL}:nth-child({col_pos}) {_BTN}'
    )

    # ── ① Active 按鈕高亮 CSS（小型動態注入）
    st.markdown(f"""
    <style>
    {_active} {{
        background : linear-gradient(160deg,
                        #bff0e8 0%, #d6f0ff 50%, #ddeeff 100%) !important;
        border     : 1.5px solid rgba(15,110,86,0.42) !important;
        color      : #085041 !important;
        font-weight: 700 !important;
    }}
    </style>
    """, unsafe_allow_html=True)

    # ── ② JS：用 inline !important 設定 3D 陰影 + hover 動效
    js = """
    <script>
    (function () {

        /* 基底 3D 陰影（inline !important，不被任何 stylesheet 覆蓋）*/
        var BASE_SHADOW =
            '0 4px 0 rgba(15,110,86,0.22),' +
            '0 7px 18px rgba(29,158,117,0.12),' +
            '0 1px 4px rgba(0,0,0,0.07),' +
            'inset 0 1.5px 0 rgba(255,255,255,0.96),' +
            'inset 0 -1.5px 0 rgba(29,158,117,0.14)';

        /* Hover 陰影 */
        var HOVER_SHADOW =
            '0 8px 0 rgba(15,110,86,0.18),' +
            '0 16px 32px rgba(29,158,117,0.20),' +
            '0 6px 12px rgba(29,158,117,0.12),' +
            'inset 0 1.5px 0 rgba(255,255,255,0.98),' +
            'inset 0 -1.5px 0 rgba(29,158,117,0.07)';

        /* 按下陰影 */
        var PRESS_SHADOW =
            '0 1px 0 rgba(15,110,86,0.26),' +
            '0 3px 8px rgba(29,158,117,0.10),' +
            'inset 0 1.5px 0 rgba(255,255,255,0.88),' +
            'inset 0 -1.5px 0 rgba(29,158,117,0.20)';

        var TRANSITION_NORMAL =
            'transform 0.28s cubic-bezier(0.22,1,0.36,1),' +
            'box-shadow 0.28s cubic-bezier(0.22,1,0.36,1),' +
            'filter 0.20s ease';

        var TRANSITION_FAST =
            'transform 0.07s cubic-bezier(0.22,1,0.36,1),' +
            'box-shadow 0.07s cubic-bezier(0.22,1,0.36,1)';

        /* 套用基底視覺（每次 setupButtons 都執行，修復切頁後 inline style 遺失）*/
        function applyBase(btn) {
            btn.style.setProperty('box-shadow',  BASE_SHADOW,       'important');
            btn.style.setProperty('transition',  TRANSITION_NORMAL, 'important');
            btn.style.setProperty('will-change', 'transform, box-shadow', 'important');
            btn.style.setProperty('transform',   'translateY(0)',    'important');
        }

        /* overflow 修復：從按鈕向上走到 sidebar，確保 translateY 可見 */
        function fixOverflow(btn) {
            var sb   = window.parent.document
                             .querySelector('[data-testid="stSidebar"]');
            var node = btn.parentElement;
            while (node && node !== sb) {
                node.style.setProperty('overflow', 'visible', 'important');
                node = node.parentElement;
            }
        }

        function setupButtons() {
            var doc     = window.parent.document;
            var sidebar = doc.querySelector('[data-testid="stSidebar"]');
            if (!sidebar) return;

            var hblocks = Array.from(
                sidebar.querySelectorAll('[data-testid="stHorizontalBlock"]')
            );

            hblocks.forEach(function (hb, idx) {
                /*if (idx === 0) return; // 跳過登出列*/

                hb.querySelectorAll(
                    'button[data-testid="stBaseButton-secondary"]'
                ).forEach(function (btn) {

                    /* 每次都重設基底樣式（關鍵：修復切頁後 inline style 清除）*/
                    fixOverflow(btn);
                    applyBase(btn);

                    /* 事件只綁一次 if (btn._navBound) return;*/
                    
                    btn._navBound = true;

                    btn.addEventListener('mouseenter', function () {
                        btn.style.setProperty('transform',  'translateY(-5px)', 'important');
                        btn.style.setProperty('filter',     'brightness(1.05)', 'important');
                        btn.style.setProperty('box-shadow', HOVER_SHADOW,       'important');
                    });

                    btn.addEventListener('mouseleave', function () {
                        btn.style.setProperty('transition', TRANSITION_NORMAL, 'important');
                        btn.style.setProperty('transform',  'translateY(0)',   'important');
                        btn.style.removeProperty('filter');
                        btn.style.setProperty('box-shadow', BASE_SHADOW,       'important');
                    });

                    btn.addEventListener('mousedown', function () {
                        btn.style.setProperty('transition', TRANSITION_FAST, 'important');
                        btn.style.setProperty('transform',  'translateY(-1px)', 'important');
                        btn.style.setProperty('box-shadow', PRESS_SHADOW,      'important');
                    });

                    btn.addEventListener('mouseup', function () {
                        btn.style.setProperty('transition', TRANSITION_NORMAL, 'important');
                        btn.style.setProperty('transform',  'translateY(-5px)', 'important');
                        btn.style.setProperty('box-shadow', HOVER_SHADOW,      'important');
                    });
                });
            });
        }

        /* 首次執行 */
        setupButtons();

        /* MutationObserver：Streamlit 任何重繪後自動重套用 */
        var timer = null;
        new MutationObserver(function () {
            clearTimeout(timer);
            timer = setTimeout(setupButtons, 80);
        }).observe(
            window.parent.document.querySelector('[data-testid="stSidebar"]') ||
            window.parent.document.body,
            { childList: true, subtree: true }
        );

    })();
    </script>
    """

    with st.empty():
        st.iframe(js, height=1)


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
                <span>Bllln Web © 2026</span>
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
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.markdown(SIDEBAR_NAV_CSS, unsafe_allow_html=True)
    new_page = render_sidebar(st.session_state.active_page)

    if new_page != st.session_state.active_page:
        st.session_state.active_page = new_page
        st.rerun()

    active_id = st.session_state.active_page
    page_cfg = PAGE_MAP.get(active_id, PAGE_CONFIG[0])

    render_page_hero(page_cfg)
    log_section(f"PAGE: {page_cfg['title'].upper()}")
    logger.info(
        "進入功能頁面 ─ id=%s  user=%s", active_id, st.session_state.get("username")
    )

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
    except ModuleNotFoundError as exc:
        st.error(f"❌ 無法載入模組：`{module_path}`\n\n{exc}")
    except Exception as exc:
        st.error(f"❌ 頁面執行發生錯誤：{exc}")

    time.sleep(0)  # 讓出事件循環
    # ⚠️ 側邊欄樣式必須在 mod.show() 之後注入，永遠壓過頁面 CSS
    _inject_sidebar_nav_style(active_id)

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
