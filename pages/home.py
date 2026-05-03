# pages/home.py
from __future__ import annotations

import logging
import datetime

import streamlit as st

from config.pages import HOME_CARDS

logger = logging.getLogger("pages.home")


def _navigate_to(page_id: str) -> None:
    """切換 active_page 並觸發重繪。"""
    st.session_state.active_page = page_id
    st.rerun()


def show() -> None:
    logger.info("渲染首頁 ─ user=%s", st.session_state.get("username"))

    username = st.session_state.get("username", "使用者")

    # ── 歡迎區塊 ─────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="
            background:linear-gradient(135deg,rgba(108,142,255,0.08),rgba(167,139,250,0.06));
            border:1px solid rgba(108,142,255,0.18);
            border-radius:12px;padding:1.2rem 1.6rem;margin-bottom:1.5rem;
        ">
            <span style="font-size:1.5rem">👋</span>
            <span style="font-size:1.1rem;font-weight:700;color:#A6A7AB;margin-left:10px">
                歡迎回來，<span style="color:#6c8eff">{username}</span>！
            </span>
            <p style="font-size:0.82rem;color:#8890a4;margin:6px 0 0">
                {datetime.datetime.now().strftime('%Y年%m月%d日 %A')} · 系統一切正常運作中
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # ── 功能導覽卡片 ─────────────────────────────────────────────
    st.subheader("🚀 快速導覽")
    st.markdown(
        "<p style='font-size:0.82rem;color:#8890a4;margin:-0.6rem 0 1rem'>點擊卡片直接跳轉至對應功能</p>",
        unsafe_allow_html=True,
    )

    # 每行最多 3 欄
    _COLS_PER_ROW = 3
    for row_start in range(0, len(HOME_CARDS), _COLS_PER_ROW):
        row_cards = HOME_CARDS[row_start : row_start + _COLS_PER_ROW]
        cols = st.columns(_COLS_PER_ROW)
        for col, card in zip(cols, row_cards):
            with col:
                # 用 HTML 渲染視覺卡片（純展示層）
                st.markdown(
                    f"""
                    <div style="
                        background:{card['accent_soft']};
                        border:1px solid {card['border_soft']};
                        border-radius:12px;
                        padding:1rem 1.1rem 0.6rem;
                        margin-bottom:0.2rem;
                        pointer-events:none;
                    ">
                        <div style="font-size:1.8rem;margin-bottom:0.3rem">{card['icon']}</div>
                        <div style="font-size:0.9rem;font-weight:700;
                            color:{card['accent']};margin-bottom:0.25rem">
                            {card['title']}
                        </div>
                        <p style="font-size:0.75rem;color:#8890a4;margin:0;
                            line-height:1.5">{card['desc']}</p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                # 實際可點擊的按鈕（緊貼卡片下方）
                if st.button(
                    f"前往 {card['title']} →",
                    key=f"home_nav_{card['id']}",
                    width='stretch',
                ):
                    logger.info("首頁導覽卡片點擊 → %s", card["id"])
                    _navigate_to(card["id"])

    st.divider()

    # ── 最新消息 ─────────────────────────────────────────────────
    logger.info("載入首頁最新消息")
    st.subheader("📋 最新消息")
    news = [
        ("2026-04-19", "🚀", "主架構全面重構，新增側邊欄導覽與統一 Log 系統。"),
        ("2026-04-18", "⚡", "系統升級完成，效能提升 30%。"),
        ("2026-04-17", "📊", "新功能「圖像超解析度」已上線，歡迎體驗。"),
        ("2026-04-15", "🔧", "維護公告：4/20 凌晨 2–4 點進行例行維護。"),
    ]
    for date, icon, content in news:
        st.markdown(
            f"""
            <div style="
                display:flex;align-items:flex-start;gap:12px;
                background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);
                border-radius:8px;padding:10px 14px;margin-bottom:6px;
            ">
                <span style="font-size:1.1rem;flex-shrink:0">{icon}</span>
                <div>
                    <span style="font-size:0.72rem;font-family:var(--mono);
                        color:#8890a4">{date}</span>
                    <p style="font-size:0.85rem;color:#e8eaf0;margin:2px 0 0">{content}</p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    logger.info("首頁渲染完成")
