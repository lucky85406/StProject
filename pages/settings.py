import streamlit as st


def show():
    st.title("⚙️ 設定")
    st.divider()

    st.subheader("👤 個人資料")
    with st.form("profile_form"):
        display_name = st.text_input("顯示名稱", value=st.session_state.username)
        email = st.text_input("電子郵件", placeholder="example@email.com")
        st.form_submit_button("儲存變更", width='stretch')

    st.divider()
    st.subheader("🔒 修改密碼")
    with st.form("password_form"):
        old_pw = st.text_input("舊密碼", type="password")
        new_pw = st.text_input("新密碼", type="password")
        confirm_pw = st.text_input("確認新密碼", type="password")
        submitted = st.form_submit_button("更新密碼")

    if submitted:
        if new_pw != confirm_pw:
            st.error("新密碼與確認密碼不一致。")
        elif len(new_pw) < 6:
            st.warning("密碼長度至少需要 6 個字元。")
        else:
            st.success("密碼已更新！（示範模式，未實際儲存）")

    st.divider()
    st.subheader("🎨 外觀偏好")
    theme = st.selectbox("介面主題", ["預設（淺色）", "深色", "自動"])
    lang = st.selectbox("語言", ["繁體中文", "English", "日本語"])
    st.info(f"目前設定：{theme}、{lang}（示範模式，未實際儲存）")
