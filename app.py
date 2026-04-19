# app.py  ──  StProject 主程式入口
# 架構：登入 → 主畫面（側邊欄導覽 + 動態參數面板 + Footer）+ 全域 Log 系統
from __future__ import annotations

import datetime
import logging
import sys
from typing import Any

import streamlit as st

from core.session_store import create_session, verify_session, delete_session
from core.users import verify_password

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
    force=True,          # 覆蓋 Streamlit 預設 handler
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


def show_login() -> None:
    log_section("LOGIN PAGE")
    logger.info("顯示登入畫面")

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)

    # 讓登入卡片置中
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

        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("👤  帳號", placeholder="請輸入帳號")
            password = st.text_input("🔒  密碼", type="password", placeholder="請輸入密碼")
            submit = st.form_submit_button("登 入", use_container_width=True)

        if submit:
            logger.info("登入嘗試 ─ user=%s", username)
            if verify_password(username, password):
                sid = create_session(username)
                st.session_state.update(logged_in=True, username=username, sid=sid)
                st.query_params["sid"] = sid
                logger.info("登入成功 ─ user=%s  sid=%s", username, sid[:8] + "…")
                log_section("MAIN APPLICATION LOADED")
                st.rerun()
            else:
                logger.warning("登入失敗 ─ user=%s  (密碼錯誤)", username)
                st.error("帳號或密碼錯誤，請重試。")

        st.markdown(
            "<div class='login-hint'>測試帳號：admin / admin123 　或　 user / user123</div>",
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
        "params": [],          # 首頁無側邊欄參數
    },
    {
        "id": "dashboard",
        "icon": "📊",
        "label": "儀表板",
        "title": "資料儀表板",
        "subtitle": "圖表分析與關鍵指標總覽",
        "module": "pages.dashboard",
        "params": [
            {"type": "selectbox", "key": "dash_range", "label": "時間範圍",
             "options": ["最近 7 天", "最近 30 天", "最近 90 天", "本年度"], "default": 0},
            {"type": "selectbox", "key": "dash_chart", "label": "圖表類型",
             "options": ["折線圖", "長條圖", "面積圖"], "default": 0},
            {"type": "checkbox", "key": "dash_animate", "label": "啟用動態效果", "default": True},
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
            {"type": "number", "key": "crawl_concurrency", "label": "最大並發數",
             "min": 1, "max": 10, "default": 3},
            {"type": "slider", "key": "crawl_delay", "label": "請求延遲 (秒)",
             "min": 0.5, "max": 5.0, "step": 0.5, "default": 1.5},
            {"type": "number", "key": "crawl_timeout", "label": "逾時時間 (秒)",
             "min": 5, "max": 60, "default": 15},
            {"type": "number", "key": "crawl_retries", "label": "最大重試次數",
             "min": 0, "max": 10, "default": 3},
            {"type": "checkbox", "key": "crawl_robots", "label": "遵守 robots.txt", "default": True},
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
            {"type": "selectbox", "key": "up_model", "label": "AI 模型",
             "options": ["EDSR", "ESPCN", "FSRCNN", "LapSRN"], "default": 0},
            {"type": "selectbox", "key": "up_scale", "label": "放大倍數",
             "options": ["2×", "3×", "4×"], "default": 0},
            {"type": "checkbox", "key": "up_gpu", "label": "啟用 GPU 加速", "default": True},
            {"type": "checkbox", "key": "up_portrait", "label": "人像細節強化模式", "default": False},
            {"type": "slider", "key": "up_sharpen", "label": "銳化強度",
             "min": 0.0, "max": 3.0, "step": 0.1, "default": 1.2},
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
        for cfg in PAGE_CONFIG if cfg["id"] == current_page_id
        for p in cfg.get("params", [])
    }
    other_keys: list[str] = [
        p["key"]
        for cfg in PAGE_CONFIG if cfg["id"] != current_page_id
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
            "font-family:\"DM Mono\",monospace;padding:0 4px'>"
            "此頁面無額外參數</p>",
            unsafe_allow_html=True,
        )
        return

    for p in params:
        ptype: str = p["type"]
        key: str   = p["key"]
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
            st.slider(label, min_value=lo, max_value=hi,
                      step=step, value=safe_val, key=key)

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
            st.number_input(label, min_value=lo_i, max_value=hi_i,
                            value=safe_val, step=1, key=key)


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
        if logout_clicked := st.button("🚪  登出", key="logout_btn", use_container_width=True):
            logger.info("使用者登出 ─ user=%s", st.session_state.get("username"))
            delete_session(st.session_state.sid)
            st.session_state.update(logged_in=False, username="", sid="")
            st.query_params.clear()
            log_section("SESSION ENDED")
            st.rerun()

        # ── 導覽按鈕（上半部）─────────────────────────────────────
        st.markdown(
            "<p style='font-size:0.58rem;font-family:\"JetBrains Mono\",monospace;"
            "color:#8890a4;text-transform:uppercase;letter-spacing:0.12em;"
            "padding:0 4px;margin:0.6rem 0 0.5rem'>▪ 功能導覽</p>",
            unsafe_allow_html=True,
        )

        # 每列最多 3 個按鈕，以 st.columns 實現
        for row_start in range(0, len(PAGE_CONFIG), 3):
            row_pages = PAGE_CONFIG[row_start: row_start + 3]
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
                            active_id, page["id"],
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
        active_id, page_cfg["title"],
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

if st.session_state.logged_in:
    show_main()
else:
    show_login()
