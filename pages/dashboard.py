# pages/dashboard.py
from __future__ import annotations

import logging
import random

import streamlit as st

logger = logging.getLogger("pages.dashboard")

try:
    import pandas as pd
    import numpy as np
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False
    logger.warning("pandas / numpy 未安裝，圖表功能降級")


def show() -> None:
    logger.info(
        "渲染儀表板 ─ user=%s  range=%s  chart=%s",
        st.session_state.get("username"),
        st.session_state.get("dash_range", "最近 7 天"),
        st.session_state.get("dash_chart", "折線圖"),
    )

    if not _HAS_PANDAS:
        st.warning("⚠️ 需要 pandas 與 numpy，請執行 `uv add pandas numpy`")
        return

    # 讀取側邊欄參數（由 app.py 統一渲染）
    date_range = st.session_state.get("dash_range", "最近 7 天")
    chart_type = st.session_state.get("dash_chart", "折線圖")

    range_map = {"最近 7 天": 7, "最近 30 天": 30, "最近 90 天": 90, "本年度": 120}
    n_days = range_map.get(date_range, 7)

    logger.info("生成圖表資料 ─ days=%d  type=%s", n_days, chart_type)

    # ── 統計卡片 ───────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    metrics = [
        ("💰 總收益", f"${random.randint(80,150):,}K", f"+{random.randint(5,18)}%"),
        ("👥 活躍用戶", f"{random.randint(1200,3500):,}", f"+{random.randint(2,12)}%"),
        ("📦 訂單數", f"{random.randint(300,800):,}", f"+{random.randint(3,20)}%"),
        ("⚡ 轉換率", f"{random.uniform(3.2,8.5):.1f}%", f"+{random.uniform(0.2,1.5):.1f}%"),
    ]
    for col, (label, value, delta) in zip([col1, col2, col3, col4], metrics):
        with col:
            st.metric(label=label, value=value, delta=delta)

    st.divider()

    # ── 主圖表 ─────────────────────────────────────────────────────
    dates = pd.date_range(end=pd.Timestamp.today(), periods=n_days, freq="D")
    df = pd.DataFrame({
        "日期": dates,
        "收益": np.cumsum(np.random.randn(n_days) * 500 + 1000) + 50000,
        "用戶數": np.random.randint(100, 400, n_days),
    }).set_index("日期")

    logger.info("圖表渲染 ─ chart_type=%s  n_rows=%d", chart_type, len(df))

    st.subheader(f"📈 {date_range}趨勢分析 — {chart_type}")
    if chart_type == "折線圖":
        st.line_chart(df)
    elif chart_type == "長條圖":
        st.bar_chart(df)
    elif chart_type == "面積圖":
        st.area_chart(df)

    st.divider()

    # ── 資料表 ─────────────────────────────────────────────────────
    logger.info("渲染資料表格 ─ rows=%d", len(df))
    with st.expander("📋 查看原始資料"):
        st.dataframe(df.reset_index(), width='stretch', height=300)

    logger.info("儀表板渲染完成")
