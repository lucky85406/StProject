# app.py
import streamlit as st
from core.session_store import create_session, verify_session, delete_session
from core.users import verify_password

st.set_page_config(
    page_title="StProject",
    page_icon="🏠",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Session 恢復邏輯（從 URL query param 讀取）────────────────────────────────
if "logged_in" not in st.session_state:
    sid = st.query_params.get("sid", "")
    username = verify_session(sid) if sid else None

    if username:
        st.session_state.logged_in = True
        st.session_state.username = username
        st.session_state.sid = sid
    else:
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.sid = ""


# ── 登入畫面 ──────────────────────────────────────────────────────────────────
def show_login() -> None:
    st.markdown(
        """
        <style>
        .title { text-align:center; font-size:2rem; font-weight:700; margin-bottom:.2rem; }
        .subtitle { text-align:center; color:#666; margin-bottom:2rem; }
        </style>""",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<p class="title">🏠 StProject</p>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">請登入以繼續使用</p>', unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("👤 帳號", placeholder="請輸入帳號")
            password = st.text_input(
                "🔒 密碼", type="password", placeholder="請輸入密碼"
            )
            submit = st.form_submit_button("登入", width='stretch')

        if submit:
            if verify_password(username, password):
                sid = create_session(username)

                # ✅ 寫入 session_state 與 URL query param
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.sid = sid
                st.query_params["sid"] = sid  # 這行讓 F5 後 URL 保留 sid
                st.rerun()
            else:
                st.error("帳號或密碼錯誤，請重試。")

    st.markdown(
        "<p style='text-align:center;color:#aaa;margin-top:3rem;font-size:.8rem;'>"
        "測試帳號：admin / admin123 　或　 user / user123</p>",
        unsafe_allow_html=True,
    )


# ── 主畫面 ────────────────────────────────────────────────────────────────────
def show_main() -> None:
    with st.sidebar:
        st.markdown(f"### 👋 你好，**{st.session_state.username}**！")
        st.divider()
        page = st.radio(
            "導覽選單",
            ["🏠 首頁", "📊 儀表板", "⚙️ 設定", "爬蟲"],
            label_visibility="collapsed",
        )
        st.divider()
        if st.button("🚪 登出", width='stretch'):
            delete_session(st.session_state.sid)
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.sid = ""
            st.query_params.clear()  # ✅ 清除 URL 裡的 sid
            st.rerun()

    if page == "🏠 首頁":
        from pages import home

        home.show()
    elif page == "📊 儀表板":
        from pages import dashboard

        dashboard.show()
    elif page == "⚙️ 設定":
        from pages import settings

        settings.show()
    elif page == "爬蟲":
        from pages import crawler_dashboard

        crawler_dashboard.show()


# ── 路由 ──────────────────────────────────────────────────────────────────────
if st.session_state.logged_in:
    show_main()
else:
    show_login()
