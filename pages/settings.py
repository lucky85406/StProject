# pages/settings.py
from __future__ import annotations

import logging
import sys
import platform

from httpx import get
import streamlit as st

from core.users import change_password,get_user_id
from core.expense_db import (
    get_budget,
    update_budget,
    get_all_categories,
    add_category,
    delete_category,
)

logger = logging.getLogger("pages.settings")

# ─────────────────────────────────────────────────────────────────────────────
#  可用 Emoji 圖示選單（供新增類別時選擇）
# ─────────────────────────────────────────────────────────────────────────────
_ICON_OPTIONS: list[str] = [
    "🍜",
    "🍔",
    "🍕",
    "🍣",
    "☕",
    "🧋",
    "🍺",
    "🚌",
    "🚗",
    "🚇",
    "✈️",
    "🛵",
    "🚕",
    "🛒",
    "👗",
    "👟",
    "💄",
    "🎁",
    "🎬",
    "🎮",
    "🎵",
    "📺",
    "🏋️",
    "⚽",
    "🏥",
    "💊",
    "🩺",
    "🏠",
    "🪴",
    "🔧",
    "💡",
    "📚",
    "📖",
    "🎓",
    "✏️",
    "💼",
    "📱",
    "💻",
    "🖨️",
    "🔖",
    "⭐",
    "🎯",
    "💰",
    "🌟",
]


# ─────────────────────────────────────────────────────────────────────────────
#  Tab｜一般設定（原有功能保留）
# ─────────────────────────────────────────────────────────────────────────────


def _tab_general() -> None:
    """個人資料、密碼修改、外觀偏好、系統資訊（原有內容）。"""

    # ── 個人資料 ──────────────────────────────────────────────────
    st.subheader("👤 個人資料")
    with st.form("profile_form"):
        display_name = st.text_input(
            "顯示名稱", value=st.session_state.get("username", "")
        )
        email = st.text_input("電子郵件", placeholder="example@email.com")
        bio = st.text_area("個人簡介", placeholder="簡單描述自己...", height=80)
        submitted_profile = st.form_submit_button("儲存變更", use_container_width=True)

    if submitted_profile:
        logger.info(
            "個人資料儲存 ─ user=%s  name=%s",
            st.session_state.get("username"),
            display_name,
        )
        st.success("✅ 個人資料已更新！（示範模式）")

    st.divider()

    # ── 修改密碼 ──────────────────────────────────────────────────
    st.subheader("🔒 修改密碼")
    with st.form("password_form"):
        old_pw = st.text_input("舊密碼", type="password")
        new_pw = st.text_input("新密碼", type="password")
        confirm_pw = st.text_input("確認新密碼", type="password")
        submitted_pw = st.form_submit_button("更新密碼", use_container_width=True)

    if submitted_pw:
        if not old_pw:
            st.warning("⚠️ 請輸入舊密碼")
        elif new_pw != confirm_pw:
            st.error("❌ 兩次密碼不一致")
        elif len(new_pw) < 6:
            st.warning("⚠️ 新密碼至少需 6 個字元")
        else:
            current_user: str = st.session_state.get("username", "")
            ok = change_password(current_user, old_pw, new_pw)
            if ok:
                st.success("✅ 密碼已更新！")
                logger.info("密碼變更成功 ─ user=%s", current_user)
            else:
                st.error("❌ 舊密碼錯誤，請重試。")

    st.divider()

    # ── 外觀偏好 ──────────────────────────────────────────────────
    st.subheader("🎨 外觀偏好")
    col1, col2 = st.columns(2)
    with col1:
        theme = st.selectbox("介面主題", ["深色（預設）", "淺色", "自動"])
    with col2:
        lang = st.selectbox("語言", ["繁體中文", "English", "日本語"])

    if st.button("套用外觀設定", use_container_width=True):
        logger.info("外觀設定套用 ─ theme=%s  lang=%s", theme, lang)
        st.info(f"🎨 已套用：{theme}、{lang}（示範模式）")

    st.divider()

    # ── 系統資訊 ──────────────────────────────────────────────────
    st.subheader("ℹ️ 系統資訊")
    import streamlit as _st

    info_cols = st.columns(3)
    with info_cols[0]:
        st.metric("Python 版本", platform.python_version())
    with info_cols[1]:
        st.metric("作業系統", platform.system())
    with info_cols[2]:
        st.metric("Streamlit 版本", _st.__version__)


# ─────────────────────────────────────────────────────────────────────────────
#  Tab｜每日預算設定（F-05）
# ─────────────────────────────────────────────────────────────────────────────


def _tab_budget() -> None:
    """每日預算上限設定與啟用/停用切換。"""
    user_id = get_user_id(st.session_state.get("username"))
    budget = get_budget(user_id)

    # ── 目前狀態卡片 ──────────────────────────────────────────────
    with st.container(border=True):
        st.markdown("**📊 目前預算狀態**")
        col_status, col_val = st.columns(2)
        with col_status:
            if budget:
                status_label = "✅ 已啟用" if budget.is_active else "⏸️ 已暫停"
                st.metric("警示狀態", status_label)
            else:
                st.metric("警示狀態", "—  未設定")
        with col_val:
            limit_display = f"NT$ {float(budget.daily_limit):,.0f}" if budget else "—"
            st.metric("每日上限", limit_display)

    st.markdown("---")

    # ── 編輯表單 ──────────────────────────────────────────────────
    st.markdown("**✏️ 修改預算設定**")

    with st.form("budget_form"):
        new_limit = st.number_input(
            "每日預算上限（NT$）",
            min_value=1.0,
            max_value=9_999_999.0,
            value=float(budget.daily_limit) if budget else 1000.0,
            step=100.0,
            format="%.0f",
            help="當日累計消費超過此金額時，系統會在新增時顯示警示。",
        )
        new_active = st.toggle(
            "啟用超標警示",
            value=budget.is_active if budget else True,
            help="關閉後仍會記錄消費，但不顯示超標提示。",
        )
        submitted = st.form_submit_button("💾 儲存預算設定", use_container_width=True)

    if submitted:
        from decimal import Decimal

        ok = update_budget(
            user_id=get_user_id(st.session_state.get("username")),
            daily_limit=Decimal(str(new_limit)),
            is_active=new_active,
        )
        if ok:
            st.success(
                f"✅ 預算已更新：NT$ {new_limit:,.0f}｜"
                f"警示{'開啟' if new_active else '關閉'}"
            )
            logger.info("預算設定更新 ─ limit=%s  active=%s", new_limit, new_active)
            st.rerun()
        else:
            st.error("❌ 儲存失敗，請確認金額大於 0。")


# ─────────────────────────────────────────────────────────────────────────────
#  Tab｜類別管理（F-02）
# ─────────────────────────────────────────────────────────────────────────────


def _render_icon_picker(form_key: str) -> str:
    """
    以按鈕網格呈現 Emoji 選擇器。
    回傳目前選中的 Emoji 字串。
    選中狀態存於 session_state[form_key + '_icon']。
    """
    state_key = f"{form_key}_icon"
    if state_key not in st.session_state:
        st.session_state[state_key] = _ICON_OPTIONS[0]

    selected: str = st.session_state[state_key]

    st.markdown(
        f"**選擇圖示**：目前選擇 " f"<span style='font-size:1.4rem'>{selected}</span>",
        unsafe_allow_html=True,
    )

    # 每列 10 個圖示
    for row_start in range(0, len(_ICON_OPTIONS), 10):
        row_icons = _ICON_OPTIONS[row_start : row_start + 10]
        cols = st.columns(len(row_icons))
        for col, icon in zip(cols, row_icons):
            with col:
                is_sel = icon == selected
                # 選中的套用 primary，其餘 secondary
                if st.button(
                    icon,
                    key=f"{form_key}_icon_{icon}",
                    type="primary" if is_sel else "secondary",
                    use_container_width=True,
                ):
                    st.session_state[state_key] = icon
                    st.rerun()

    return selected


def _tab_categories() -> None:
    """類別管理：預設類別展示 + 新增自訂類別 + 刪除自訂類別。"""
    user_id = get_user_id(st.session_state.get("username"))
    categories = get_all_categories(user_id)
    default_cats = [c for c in categories if c.is_default]
    custom_cats = [c for c in categories if not c.is_default]

    # ── 預設類別（唯讀展示）─────────────────────────────────────
    with st.container(border=True):
        st.markdown(
            "**🔒 預設類別**"
            "<span style='font-size:0.72rem;color:#8b85a8;"
            'font-family:"DM Mono",monospace;margin-left:8px\'>'
            "不可刪除</span>",
            unsafe_allow_html=True,
        )
        cols = st.columns(4)
        for i, cat in enumerate(default_cats):
            with cols[i % 4]:
                st.markdown(
                    f"<div style='text-align:center;padding:0.5rem;"
                    f"background:rgba(124,111,247,0.06);"
                    f"border:1px solid rgba(124,111,247,0.14);"
                    f"border-radius:10px;margin-bottom:0.4rem'>"
                    f"<div style='font-size:1.4rem'>{cat.icon}</div>"
                    f"<div style='font-size:0.75rem;color:#3b3552;"
                    f"font-weight:600'>{cat.name}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    # ── 自訂類別（可刪除）──────────────────────────────────────
    st.markdown("**🏷️ 自訂類別**")

    if not custom_cats:
        st.markdown(
            "<p style='font-size:0.82rem;color:#8b85a8'>尚無自訂類別，"
            "可於下方新增。</p>",
            unsafe_allow_html=True,
        )
    else:
        for cat in custom_cats:
            col_icon, col_name, col_del = st.columns([1, 5, 1])
            with col_icon:
                st.markdown(
                    f"<div style='font-size:1.5rem;text-align:center;"
                    f"padding-top:0.3rem'>{cat.icon}</div>",
                    unsafe_allow_html=True,
                )
            with col_name:
                st.markdown(
                    f"<div style='padding-top:0.5rem;font-weight:600;"
                    f"color:#3b3552'>{cat.name}</div>",
                    unsafe_allow_html=True,
                )
            with col_del:
                del_flag = f"cat_del_{cat.id}"
                if st.session_state.get(del_flag):
                    # 二次確認
                    if st.button(
                        "✓",
                        key=f"cat_del_ok_{cat.id}",
                        help="確認刪除",
                        use_container_width=True,
                        type="primary",
                    ):
                        ok = delete_category(cat.id)
                        if ok:
                            st.session_state.pop(del_flag, None)
                            st.toast(f"已刪除類別「{cat.name}」", icon="🗑️")
                            logger.info(
                                "刪除自訂類別 ─ id=%s  name=%s", cat.id, cat.name
                            )
                            st.rerun()
                        else:
                            st.error("❌ 刪除失敗")
                else:
                    if st.button(
                        "🗑️",
                        key=f"cat_del_{cat.id}_btn",
                        help=f"刪除「{cat.name}」",
                        use_container_width=True,
                    ):
                        st.session_state[del_flag] = True
                        st.rerun()

    st.markdown("---")

    # ── 新增自訂類別 ─────────────────────────────────────────────
    st.markdown("**➕ 新增自訂類別**")

    with st.container(border=True):
        new_name = st.text_input(
            "類別名稱（最多 20 字）",
            max_chars=20,
            placeholder="例如：寵物、旅遊...",
            key="new_cat_name",
        )
        selected_icon = _render_icon_picker("new_cat")
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button(
            "➕ 新增類別",
            use_container_width=True,
            type="primary",
            key="new_cat_submit",
        ):
            name_clean = new_name.strip()
            if not name_clean:
                st.error("❌ 類別名稱不可為空白")
            elif len(name_clean) > 20:
                st.error("❌ 名稱不可超過 20 字")
            else:
                ok = add_category(name=name_clean, icon=selected_icon)
                if ok:
                    st.toast(f"已新增類別「{name_clean}」{selected_icon}", icon="✅")
                    logger.info(
                        "新增自訂類別 ─ name=%s  icon=%s", name_clean, selected_icon
                    )
                    # 清除輸入欄
                    st.session_state.pop("new_cat_name", None)
                    st.session_state.pop("new_cat_icon", None)
                    st.rerun()
                else:
                    st.error(f"❌ 新增失敗，「{name_clean}」可能已存在。")

# pages/settings.py — 新增設備管理段落（加在既有設定頁末尾）


def _show_device_management(username: str) -> None:
    from core.device_auth import (
        compute_device_hash,
        has_any_device,
        list_devices,
        register_device,
        revoke_device,
    )

    st.subheader("📱 QR 登入設備管理")
    st.caption("綁定後，掃描 QR Code 只需輸入帳號即可登入，無需密碼。")

    # ── 已綁定設備列表 ────────────────────────────────────────────
    devices: list[dict] = list_devices(username)
    if devices:
        for dev in devices:
            col_label, col_time, col_btn = st.columns([3, 3, 1])
            with col_label:
                st.markdown(f"📲 **{dev['device_label']}**")
            with col_time:
                last = dev.get("last_used_at") or "從未使用"
                st.caption(f"最後使用：{str(last)[:19]}")
            with col_btn:
                if st.button("撤銷", key=f"revoke_{dev['id']}", type="secondary"):
                    if revoke_device(dev["id"], username):
                        st.success("✅ 設備已撤銷")
                        st.rerun()
                    else:
                        st.error("❌ 撤銷失敗")
    else:
        st.info("目前尚未綁定任何設備。")

    st.divider()

    # ── 綁定當前設備 ─────────────────────────────────────────────
    st.markdown("**綁定目前使用的設備**")

    # ✅ 改用 st.context.headers，伺服器端直接讀取，無 JS 時序問題
    _headers = st.context.headers
    _ua = _headers.get("User-Agent", "")
    _lang = _headers.get("Accept-Language", "")
    _fp_raw = f"{_ua}|{_lang}"

    # 顯示偵測到的設備資訊（方便使用者確認）
    if _ua:
        st.caption(f"🔍 偵測到：`{_ua[:80]}{'…' if len(_ua) > 80 else ''}`")

    _label: str = st.text_input(
        "設備名稱",
        placeholder="例：iPhone 16 Pro / 辦公室 MacBook",
        max_chars=50,
        key="device_label_input",
    )

    if st.button("➕ 綁定此設備", type="primary", key="bind_device_btn"):
        if not _fp_raw or len(_fp_raw) < 10:
            st.error("❌ 無法取得設備資訊，請確認瀏覽器未封鎖 User-Agent。")
        elif not _label.strip():
            st.warning("⚠️ 請輸入設備名稱。")
        else:
            _hash = compute_device_hash(_fp_raw)
            ok, reason = register_device(username, _hash, _label.strip())
            if ok:
                st.success(f"✅ 設備「{_label}」已成功綁定！")
                st.rerun()
            elif reason == "already_bound":
                st.info("ℹ️ 此設備已綁定至您的帳號。")
            else:
                st.error("❌ 綁定失敗，請稍後再試。")


# ─────────────────────────────────────────────────────────────────────────────
#  頁面主函式
# ─────────────────────────────────────────────────────────────────────────────


def show() -> None:
    logger.info("渲染設定頁 ─ user=%s", st.session_state.get("username"))

    tab_general, tab_budget, tab_categories, tab_device = st.tabs(
        [
            "⚙️ 一般設定",
            "💰 每日預算",
            "🏷️ 類別管理",
            "📱 行動設備註冊",
        ]
    )

    with tab_general:
        _tab_general()

    with tab_budget:
        _tab_budget()

    with tab_categories:
        _tab_categories()

    with tab_device:
        _show_device_management(st.session_state.get("username"))

    logger.info("設定頁渲染完成")
