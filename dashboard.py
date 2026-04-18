import streamlit as st
import pandas as pd
import numpy as np


def show():
    st.title("📊 儀表板")
    st.markdown("以下為示範資料圖表，可依需求替換為真實資料來源。")
    st.divider()

    # 折線圖
    st.subheader("📈 每月數據趨勢")
    months = ["1月", "2月", "3月", "4月", "5月", "6月"]
    df_line = pd.DataFrame(
        {
            "銷售額": np.random.randint(50, 150, size=6),
            "訪客數": np.random.randint(30, 120, size=6),
        },
        index=months,
    )
    st.line_chart(df_line)

    st.divider()

    # 長條圖
    st.subheader("📊 各部門績效")
    departments = ["業務部", "工程部", "行銷部", "客服部"]
    df_bar = pd.DataFrame(
        {"績效分數": np.random.randint(60, 100, size=4)},
        index=departments,
    )
    st.bar_chart(df_bar)
