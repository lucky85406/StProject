# pages/settings.py
from __future__ import annotations

import logging

import streamlit as st

logger = logging.getLogger("pages.settings")


def show() -> None:
    logger.info("渲染設定頁 ─ user=%s", st.session_state.get("username"))

    # ── 個人資料 ───────────────────────────────────────────────────
    st.subheader("👤 個人資料")
    with st.form("profile_form"):
        display_name = st.text_input("顯示名稱", value=st.session_state.get("username", ""))
        email = st.text_input("電子郵件", placeholder="example@email.com")
        bio = st.text_area("個人簡介", placeholder="簡單描述自己...", height=80)
        submitted_profile = st.form_submit_button("儲存變更", width='stretch')

    if submitted_profile:
        logger.info("個人資料儲存 ─ user=%s  name=%s  email=%s",
                    st.session_state.get("username"), display_name, email)
        st.success("✅ 個人資料已更新！（示範模式）")

    st.divider()

    # ── 修改密碼 ───────────────────────────────────────────────────
    st.subheader("🔒 修改密碼")
    with st.form("password_form"):
        old_pw = st.text_input("舊密碼", type="password")
        new_pw = st.text_input("新密碼", type="password")
        confirm_pw = st.text_input("確認新密碼", type="password")
        submitted_pw = st.form_submit_button("更新密碼", width='stretch')

    if submitted_pw:
        logger.info("密碼修改請求 ─ user=%s", st.session_state.get("username"))
        if not old_pw:
            st.warning("⚠️ 請輸入舊密碼")
            logger.warning("密碼修改失敗 ─ 舊密碼為空")
        elif new_pw != confirm_pw:
            st.error("❌ 新密碼與確認密碼不一致")
            logger.warning("密碼修改失敗 ─ 密碼確認不符")
        elif len(new_pw) < 6:
            st.warning("⚠️ 密碼長度至少需要 6 個字元")
            logger.warning("密碼修改失敗 ─ 密碼過短 len=%d", len(new_pw))
        else:
            logger.info("密碼修改成功（示範模式）─ user=%s", st.session_state.get("username"))
            st.success("✅ 密碼已更新！（示範模式）")

    st.divider()

    # ── 外觀偏好 ───────────────────────────────────────────────────
    st.subheader("🎨 外觀偏好")
    col1, col2 = st.columns(2)
    with col1:
        theme = st.selectbox("介面主題", ["深色（預設）", "淺色", "自動"])
    with col2:
        lang = st.selectbox("語言", ["繁體中文", "English", "日本語"])

    if st.button("套用外觀設定", width='stretch'):
        logger.info("外觀設定套用 ─ theme=%s  lang=%s", theme, lang)
        st.info(f"🎨 已套用：{theme}、{lang}（示範模式）")

    st.divider()

    # ── 系統資訊 ───────────────────────────────────────────────────
    st.subheader("ℹ️ 系統資訊")
    import sys, platform
    info_cols = st.columns(3)
    with info_cols[0]:
        st.metric("Python 版本", platform.python_version())
    with info_cols[1]:
        st.metric("作業系統", platform.system())
    with info_cols[2]:
        import streamlit
        st.metric("Streamlit 版本", streamlit.__version__)

    logger.info("設定頁渲染完成")
