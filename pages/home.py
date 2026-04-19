# pages/home.py
from __future__ import annotations

import logging
import datetime

import streamlit as st

logger = logging.getLogger("pages.home")


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
            <span style="font-size:1.1rem;font-weight:700;color:#e8eaf0;margin-left:10px">
                歡迎回來，<span style="color:#6c8eff">{username}</span>！
            </span>
            <p style="font-size:0.82rem;color:#8890a4;margin:6px 0 0">
                {datetime.datetime.now().strftime('%Y年%m月%d日 %A')} · 系統一切正常運作中
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 指標卡片 ─────────────────────────────────────────────────
    logger.info("載入首頁指標卡片")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="📈 今日訪客", value="128", delta="+12")
    with col2:
        st.metric(label="📋 待處理任務", value="5", delta="-3")
    with col3:
        st.metric(label="✅ 完成率", value="84%", delta="+6%")

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
