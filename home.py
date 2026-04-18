import streamlit as st


def show():
    st.title("🏠 首頁")
    st.markdown(f"歡迎回來，**{st.session_state.username}**！")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="今日訪客", value="128", delta="+12")
    with col2:
        st.metric(label="待處理任務", value="5", delta="-3")
    with col3:
        st.metric(label="完成率", value="84%", delta="+6%")

    st.divider()
    st.subheader("📋 最新消息")
    news = [
        ("2026-04-18", "系統升級完成，效能提升 30%。"),
        ("2026-04-17", "新功能「儀表板」已上線，歡迎體驗。"),
        ("2026-04-15", "維護公告：4/20 凌晨 2–4 點進行例行維護。"),
    ]
    for date, content in news:
        st.markdown(f"- **{date}**　{content}")
