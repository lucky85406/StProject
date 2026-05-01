# pages/settings.py
from __future__ import annotations

import logging

import streamlit as st

from core.users import change_password  # 加在檔案頂部 import

logger = logging.getLogger("pages.settings")


def show() -> None:
    logger.info("渲染設定頁 ─ user=%s", st.session_state.get("username"))

    # ── 個人資料 ───────────────────────────────────────────────────
    st.subheader("👤 個人資料")
    with st.form("profile_form"):
        display_name = st.text_input(
            "顯示名稱", value=st.session_state.get("username", "")
        )
        email = st.text_input("電子郵件", placeholder="example@email.com")
        bio = st.text_area("個人簡介", placeholder="簡單描述自己...", height=80)
        submitted_profile = st.form_submit_button("儲存變更", width="stretch")

    if submitted_profile:
        logger.info(
            "個人資料儲存 ─ user=%s  name=%s  email=%s",
            st.session_state.get("username"),
            display_name,
            email,
        )
        st.success("✅ 個人資料已更新！（示範模式）")

    st.divider()

    # ── 修改密碼 ───────────────────────────────────────────────────
    st.subheader("🔒 修改密碼")
    with st.form("password_form"):
        old_pw = st.text_input("舊密碼", type="password")
        new_pw = st.text_input("新密碼", type="password")
        confirm_pw = st.text_input("確認新密碼", type="password")
        submitted_pw = st.form_submit_button("更新密碼", width="stretch")

    if submitted_pw:
        if not old_pw:
            st.warning("⚠️ 請輸入舊密碼")
        elif new_pw != confirm_pw:
            st.error("❌ 新密碼與確認密碼不一致")
        elif len(new_pw) < 6:
            st.warning("⚠️ 密碼長度至少需要 6 個字元")
        else:
            current_user = st.session_state.get("username", "")
            if change_password(current_user, old_pw, new_pw):
                st.success("✅ 密碼已更新！")
            else:
                st.error("❌ 舊密碼錯誤，請重試")

    st.divider()

    # ── Google 驗證器 (TOTP) ───────────────────────────────────────
    st.subheader("🔐 Google 驗證器 (2FA)")

    from core.users import get_totp_info, save_totp_secret, disable_totp
    from core.totp import generate_secret, generate_setup_qr_png, verify_code

    current_user: str = st.session_state.get("username", "")
    totp_enabled, _existing_secret = get_totp_info(current_user)

    if not totp_enabled:
        # ── 未啟用：引導設定流程 ──────────────────────────────────
        st.info("⚠️ 您尚未啟用 Google 驗證器，建議啟用以強化帳號安全。")

        if st.button("🛡️ 啟用 Google 驗證器", key="totp_setup_btn"):
            # 產生新 secret 並暫存於 session（尚未寫入 DB）
            st.session_state.totp_setup_secret = generate_secret()

        if pending := st.session_state.get("totp_setup_secret"):
            st.markdown("**Step 1** — 開啟 Google Authenticator，掃描下方 QR Code：")
            qr_png = generate_setup_qr_png(pending, current_user)
            col_qr, col_key = st.columns([1, 1])
            with col_qr:
                st.image(qr_png, caption="用 Google Authenticator 掃描", width=200)
            with col_key:
                st.markdown("**或手動輸入密鑰：**")
                st.code(pending, language=None)
                st.caption("請妥善保存此密鑰，停用後無法復原。")

            st.markdown("**Step 2** — 輸入 App 中產生的 6 位數驗證碼以確認設定：")
            with st.form("totp_confirm_form"):
                confirm_code = st.text_input(
                    "驗證碼", max_chars=6, placeholder="輸入 6 位數"
                )
                confirm_submit = st.form_submit_button(
                    "✅ 確認啟用", use_container_width=True
                )

            if confirm_submit:
                if verify_code(pending, confirm_code):
                    if save_totp_secret(current_user, pending):
                        st.success("🎉 Google 驗證器已成功啟用！")
                        st.session_state.pop("totp_setup_secret", None)
                        logger.info("TOTP 啟用成功 ─ user=%s", current_user)
                        st.rerun()
                    else:
                        st.error("❌ 儲存失敗，請稍後再試。")
                else:
                    st.error("❌ 驗證碼錯誤，請確認 App 時間同步後重試。")
    else:
        # ── 已啟用：顯示狀態 + 停用選項 ──────────────────────────
        st.success("✅ Google 驗證器已啟用，您的帳號受到雙重驗證保護。")

        with st.expander("⚠️ 停用 Google 驗證器（危險操作）"):
            st.warning("停用後帳號安全性將降低，請確認您的決定。")
            with st.form("totp_disable_form"):
                disable_totp_code = st.text_input(
                    "請輸入目前的 Google 驗證碼以確認身份",
                    max_chars=6,
                    placeholder="6 位數驗證碼",
                )
                disable_submit = st.form_submit_button(
                    "確認停用", type="primary", use_container_width=True
                )

            if disable_submit:
                _, current_secret = get_totp_info(current_user)
                if verify_code(current_secret or "", disable_totp_code):
                    if disable_totp(current_user):
                        st.success("Google 驗證器已停用。")
                        logger.info("TOTP 停用成功 ─ user=%s", current_user)
                        st.rerun()
                    else:
                        st.error("❌ 操作失敗，請稍後再試。")
                else:
                    st.error("❌ 驗證碼錯誤，請重試。")

    # ── 外觀偏好 ───────────────────────────────────────────────────
    st.subheader("🎨 外觀偏好")
    col1, col2 = st.columns(2)
    with col1:
        theme = st.selectbox("介面主題", ["深色（預設）", "淺色", "自動"])
    with col2:
        lang = st.selectbox("語言", ["繁體中文", "English", "日本語"])

    if st.button("套用外觀設定", width="stretch"):
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
