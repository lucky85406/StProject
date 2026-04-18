import streamlit as st

# ── 頁面設定 ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="StProject",
    page_icon="🏠",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── 假設使用者資料（可換成資料庫） ────────────────────────────────────────────
USERS = {
    "admin": "admin123",
    "user": "user123",
}

# ── Session 初始化 ─────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""


# ── 登入畫面 ───────────────────────────────────────────────────────────────────
def show_login():
    st.markdown(
        """
        <style>
        .login-box {
            max-width: 400px;
            margin: auto;
            padding: 2rem;
        }
        .title {
            text-align: center;
            font-size: 2rem;
            font-weight: 700;
            margin-bottom: 0.2rem;
        }
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown('<div class="login-box">', unsafe_allow_html=True)
        st.markdown('<p class="title">🏠 StProject</p>', unsafe_allow_html=True)
        st.markdown('<p class="subtitle">請登入以繼續使用</p>', unsafe_allow_html=True)

        with st.form("login_form"):
            username = st.text_input("👤 帳號", placeholder="請輸入帳號")
            password = st.text_input("🔒 密碼", type="password", placeholder="請輸入密碼")
            submit = st.form_submit_button("登入", use_container_width=True)

        if submit:
            if username in USERS and USERS[username] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.success("登入成功！")
                st.rerun()
            else:
                st.error("帳號或密碼錯誤，請重試。")

        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        "<p style='text-align:center; color:#aaa; margin-top:3rem; font-size:0.8rem;'>"
        "測試帳號：admin / admin123 　或　 user / user123"
        "</p>",
        unsafe_allow_html=True,
    )


# ── 主畫面 ─────────────────────────────────────────────────────────────────────
def show_main():
    # 側邊欄
    with st.sidebar:
        st.markdown(f"### 👋 你好，**{st.session_state.username}**！")
        st.divider()
        page = st.radio(
            "導覽選單",
            ["🏠 首頁", "📊 儀表板", "⚙️ 設定"],
            label_visibility="collapsed",
        )
        st.divider()
        if st.button("🚪 登出", use_container_width=True):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()

    # 頁面內容
    if page == "🏠 首頁":
        from pages import home
        home.show()
    elif page == "📊 儀表板":
        from pages import dashboard
        dashboard.show()
    elif page == "⚙️ 設定":
        from pages import settings
        settings.show()


# ── 路由 ───────────────────────────────────────────────────────────────────────
if st.session_state.logged_in:
    show_main()
else:
    show_login()
