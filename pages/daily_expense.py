# pages/daily_expense.py
"""
每日消費記錄頁面
實作範圍：
  F-01 快速新增消費
  F-03 當日消費總覽
  F-04 歷史記錄查詢（日期區間 + 類別篩選 + 編輯 / 軟刪除）
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional
from core.users import get_user_id

import streamlit as st

from core.expense_db import (
    Category,
    Expense,
    TodaySummary,
    add_expense,
    get_all_categories,
    get_expense_by_id,
    get_expenses,
    get_today_summary,
    soft_delete_expense,
    update_expense,
)

logger = logging.getLogger("pages.daily_expense")

# ─────────────────────────────────────────────────────────────────────────────
#  頁面 CSS
# ─────────────────────────────────────────────────────────────────────────────
_PAGE_CSS = """
<style>
/* ── KPI 卡片 ───────────────────────────────────────────────────── */
.exp-kpi-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 1rem;
    margin-bottom: 1.5rem;
}
.exp-kpi-card {
    background: #ffffff;
    border: 1px solid rgba(124,111,247,0.14);
    border-radius: 14px;
    padding: 1.2rem 1.4rem;
    position: relative;
    overflow: hidden;
    box-shadow: 0 2px 12px rgba(124,111,247,0.06);
    transition: border-color 0.25s, box-shadow 0.25s;
}
.exp-kpi-card:hover {
    border-color: rgba(124,111,247,0.30);
    box-shadow: 0 4px 20px rgba(124,111,247,0.12);
}
.exp-kpi-card .kpi-bar {
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
}
.exp-kpi-card .kpi-label {
    font-size: 0.65rem; font-family: 'DM Mono', monospace;
    color: #8b85a8; text-transform: uppercase;
    letter-spacing: 0.10em; margin-bottom: 0.5rem;
}
.exp-kpi-card .kpi-value {
    font-size: 1.8rem; font-weight: 800; line-height: 1.1; margin-bottom: 0.2rem;
}
.exp-kpi-card .kpi-sub { font-size: 0.72rem; color: #8b85a8; }

/* ── 預算橫幅 ───────────────────────────────────────────────────── */
.exp-budget-warn {
    background: linear-gradient(135deg,rgba(239,68,68,0.08),rgba(239,68,68,0.04));
    border: 1px solid rgba(239,68,68,0.30); border-radius: 12px;
    padding: 0.9rem 1.2rem; margin-bottom: 1.2rem;
    display: flex; align-items: center; gap: 10px;
    font-size: 0.85rem; color: #ef4444; font-weight: 600;
}
.exp-budget-ok {
    background: linear-gradient(135deg,rgba(16,185,129,0.08),rgba(16,185,129,0.04));
    border: 1px solid rgba(16,185,129,0.25); border-radius: 12px;
    padding: 0.9rem 1.2rem; margin-bottom: 1.2rem;
    display: flex; align-items: center; gap: 10px;
    font-size: 0.85rem; color: #10b981; font-weight: 600;
}

/* ── 快速新增表單卡片 ───────────────────────────────────────────── */
.exp-form-card {
    background: #ffffff;
    border: 1px solid rgba(124,111,247,0.16);
    border-radius: 16px; padding: 1.6rem; margin-bottom: 1.5rem;
    box-shadow: 0 2px 16px rgba(124,111,247,0.07);
}
.exp-form-title {
    font-size: 0.75rem; font-family: 'DM Mono', monospace;
    background: linear-gradient(135deg,#7c6ff7,#e879a0);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    text-transform: uppercase; letter-spacing: 0.10em;
    margin-bottom: 1rem;
}

/* ── 消費明細列表項目 ───────────────────────────────────────────── */
.exp-item {
    background: #ffffff;
    border: 1px solid rgba(124,111,247,0.10);
    border-radius: 12px; padding: 0.9rem 1.1rem; margin-bottom: 0.5rem;
    display: flex; align-items: center; gap: 12px;
    transition: border-color 0.2s, box-shadow 0.2s;
}
.exp-item:hover {
    border-color: rgba(124,111,247,0.25);
    box-shadow: 0 2px 10px rgba(124,111,247,0.08);
}
.exp-item-icon {
    width: 38px; height: 38px;
    background: linear-gradient(135deg,rgba(124,111,247,0.12),rgba(232,121,160,0.10));
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.2rem; flex-shrink: 0;
}
.exp-item-info { flex: 1; min-width: 0; }
.exp-item-cat {
    font-size: 0.72rem; font-family: 'DM Mono', monospace;
    color: #8b85a8; text-transform: uppercase; letter-spacing: 0.06em;
}
.exp-item-note {
    font-size: 0.82rem; color: #3b3552;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.exp-item-time { font-size: 0.68rem; font-family: 'DM Mono', monospace; color: #b8b2d0; }
.exp-item-amount { font-size: 1.1rem; font-weight: 800; color: #7c6ff7; white-space: nowrap; }

/* ── 歷史篩選工具列 ─────────────────────────────────────────────── */
.hist-toolbar {
    background: #ffffff;
    border: 1px solid rgba(124,111,247,0.12);
    border-radius: 14px; padding: 1.1rem 1.3rem; margin-bottom: 1.2rem;
    box-shadow: 0 2px 10px rgba(124,111,247,0.05);
}
.hist-section-label {
    font-size: 0.65rem; font-family: 'DM Mono', monospace;
    color: #8b85a8; text-transform: uppercase; letter-spacing: 0.10em;
    margin-bottom: 0.8rem;
}

/* ── 歷史統計小卡 ───────────────────────────────────────────────── */
.hist-stat-row {
    display: flex; gap: 0.8rem; margin-bottom: 1.2rem; flex-wrap: wrap;
}
.hist-stat-chip {
    background: rgba(124,111,247,0.08);
    border: 1px solid rgba(124,111,247,0.16);
    border-radius: 999px; padding: 0.35rem 0.9rem;
    font-size: 0.78rem; font-weight: 600; color: #7c6ff7;
    display: flex; align-items: center; gap: 6px;
}

/* ── 空白狀態 ───────────────────────────────────────────────────── */
.exp-empty {
    text-align: center; padding: 2.5rem 1rem; color: #8b85a8;
    background: rgba(124,111,247,0.03);
    border: 1px dashed rgba(124,111,247,0.18); border-radius: 14px;
}
.exp-empty .empty-icon { font-size: 2.5rem; margin-bottom: 0.6rem; }
.exp-empty .empty-text { font-size: 0.85rem; }
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid rgba(124, 111, 247, 0.20) !important;
    border-radius: 14px !important;
    box-shadow: 0 2px 12px rgba(124, 111, 247, 0.06) !important;
}
</style>
"""

_MOBILE_CSS = """
<style>
/* ══════════════════════════════════════════════════════
   📱 Mobile Responsive — 手機優化樣式
   適用寬度 ≤ 768px（手機 / 小螢幕平板）
══════════════════════════════════════════════════════ */

@media (max-width: 768px) {

  /* ── KPI 卡片：3欄改成 1欄垂直堆疊 ── */
  .exp-kpi-row {
    grid-template-columns: 1fr !important;
    gap: 0.6rem !important;
  }
  .exp-kpi-card {
    padding: 1rem 1.1rem !important;
  }
  .exp-kpi-card .kpi-value {
    font-size: 1.5rem !important;
  }

  /* ── 表單卡片：加大 padding，方便手指操作 ── */
  .exp-form-card {
    padding: 1.2rem !important;
    border-radius: 12px !important;
  }

  /* ── 消費明細列表：優化行高與字體 ── */
  .exp-item {
    padding: 1rem 0.9rem !important;
    gap: 10px !important;
    border-radius: 10px !important;
  }
  .exp-item-icon {
    width: 42px !important;
    height: 42px !important;
    font-size: 1.3rem !important;
  }
  .exp-item-cat  { font-size: 0.68rem !important; }
  .exp-item-note { font-size: 0.85rem !important; }
  .exp-item-amount {
    font-size: 1.15rem !important;
    font-weight: 800 !important;
  }

  /* ── 預算橫幅：縮小字體 ── */
  .exp-budget-warn,
  .exp-budget-ok {
    font-size: 0.80rem !important;
    padding: 0.75rem 1rem !important;
  }

  /* ── 歷史篩選工具列 ── */
  .hist-toolbar {
    padding: 0.9rem 1rem !important;
    border-radius: 12px !important;
  }

  /* ── Streamlit 原生元件在手機的覆蓋 ── */
  /* 數字輸入框放大，防止 iOS 自動縮放 */
  input[type="number"],
  input[type="text"],
  textarea {
    font-size: 16px !important;   /* iOS 低於 16px 會觸發縮放 */
  }

  /* 按鈕加高，符合 iOS HIG 44pt 最小觸控高度 */
  [data-testid="stBaseButton-primary"],
  [data-testid="stBaseButton-secondary"] {
    min-height: 48px !important;
    font-size: 0.95rem !important;
  }

  /* Tabs 標籤字體縮小以防換行 */
  [data-testid="stTabs"] button {
    font-size: 0.82rem !important;
    padding: 0.5rem 0.8rem !important;
  }

  /* 空白狀態卡片 */
  .exp-empty {
    padding: 2rem 0.8rem !important;
  }
  .exp-empty .empty-icon { font-size: 2rem !important; }
}

/* ── 超窄手機（≤ 390px）追加補強 ── */
@media (max-width: 390px) {
  .exp-kpi-card .kpi-value {
    font-size: 1.3rem !important;
  }
  .hist-stat-row {
    flex-direction: column !important;
    gap: 0.5rem !important;
  }
}
</style>
"""


# ─────────────────────────────────────────────────────────────────────────────
#  共用 Helper
# ─────────────────────────────────────────────────────────────────────────────


def _expense_list_item_html(exp: Expense, time_fmt: str = "%H:%M") -> str:
    """產生單筆消費的 HTML 卡片（純展示用，不含互動按鈕）。"""
    note_display = exp.note if exp.note else "（無備註）"
    time_str = exp.recorded_at.strftime(time_fmt)
    return (
        f'<div class="exp-item">'
        f'  <div class="exp-item-icon">{exp.category_icon}</div>'
        f'  <div class="exp-item-info">'
        f'    <div class="exp-item-cat">{exp.category_name}</div>'
        f'    <div class="exp-item-note">{note_display}</div>'
        f'    <div class="exp-item-time">{time_str}</div>'
        f"  </div>"
        f'  <div class="exp-item-amount">NT$ {float(exp.amount):,.0f}</div>'
        f"</div>"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Tab 1｜今日總覽（F-03）+ 快速新增（F-01）
# ─────────────────────────────────────────────────────────────────────────────


def _render_kpi_cards(summary: TodaySummary) -> None:
    total = float(summary.total)
    count = len(summary.expenses)
    budget = float(summary.budget_limit) if summary.budget_limit else None
    remain = (budget - total) if budget else None
    remain_color = (
        "#ef4444"
        if remain is not None and remain < 0
        else "#10b981" if remain is not None else "#7c6ff7"
    )
    remain_text = (
        f"NT$ {abs(remain):,.0f} {'超出' if remain < 0 else '剩餘'}"
        if remain is not None
        else "未設定預算"
    )
    st.markdown(
        f"""
        <div class="exp-kpi-row">
          <div class="exp-kpi-card">
            <div class="kpi-bar" style="background:linear-gradient(90deg,#7c6ff7,#e879a0)"></div>
            <div class="kpi-label">今日支出</div>
            <div class="kpi-value" style="color:#7c6ff7">NT$ {total:,.0f}</div>
            <div class="kpi-sub">{count} 筆消費記錄</div>
          </div>
          <div class="exp-kpi-card">
            <div class="kpi-bar" style="background:linear-gradient(90deg,#60a5fa,#7c6ff7)"></div>
            <div class="kpi-label">每日預算</div>
            <div class="kpi-value" style="color:#60a5fa">
              {"NT$ {:,.0f}".format(budget) if budget else "—"}
            </div>
            <div class="kpi-sub">{"已啟用" if budget else "尚未設定"}</div>
          </div>
          <div class="exp-kpi-card">
            <div class="kpi-bar"
                 style="background:linear-gradient(90deg,{remain_color},{remain_color}88)"></div>
            <div class="kpi-label">預算狀態</div>
            <div class="kpi-value" style="color:{remain_color};font-size:1.3rem">
              {remain_text}
            </div>
            <div class="kpi-sub">
              {"⚠️ 已超出上限" if summary.is_over_budget else "✅ 在預算內"}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_budget_banner(summary: TodaySummary) -> None:
    if summary.budget_limit is None:
        return
    if summary.is_over_budget:
        over_amt = float(summary.total - summary.budget_limit)
        st.markdown(
            f'<div class="exp-budget-warn">🔴 &nbsp;今日消費已超出預算 '
            f"<strong>NT$ {over_amt:,.0f}</strong>，請注意！</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="exp-budget-ok">🟢 &nbsp;今日消費在預算範圍內，繼續保持！</div>',
            unsafe_allow_html=True,
        )


def _render_add_form(categories: list[Category], user_id: str) -> bool:
    """快速新增表單，回傳 True 表示送出成功。"""
    if not categories:
        st.warning("⚠️ 無法載入類別資料，請檢查資料庫連線。")
        return False
    with st.container(border=True):
        st.markdown(
            '<div class="exp-form-title">✦ 快速新增消費</div>',
            unsafe_allow_html=True,
        )

        # Step 1：金額
        st.markdown("**① 輸入金額**")
        amount_input: float = st.number_input(
            "消費金額（NT$）",
            min_value=0.0,
            max_value=9_999_999.0,
            value=0.0,
            step=1.0,
            format="%.0f",
            label_visibility="collapsed",
            key="exp_amount",
        )

        # Step 2：類別
        st.markdown("**② 選擇類別**")
        if "exp_selected_cat" not in st.session_state:
            st.session_state.exp_selected_cat = categories[0].id

        for row_start in range(0, len(categories), 4):
            row_cats = categories[row_start : row_start + 4]
            cols = st.columns(len(row_cats))
            for col, cat in zip(cols, row_cats):
                with col:
                    is_selected = st.session_state.exp_selected_cat == cat.id
                    if st.button(
                        f"{cat.icon}\n{cat.name}",
                        key=f"cat_sel_{cat.id}",
                        use_container_width=True,
                        type="primary" if is_selected else "secondary",
                    ):
                        st.session_state.exp_selected_cat = cat.id
                        st.rerun()

        selected_cat_id: str = st.session_state.exp_selected_cat

        # Step 3：備註
        st.markdown("**③ 備註（選填）**")
        note: str = st.text_input(
            "備註",
            max_chars=200,
            placeholder="最多 200 字，可略過...",
            label_visibility="collapsed",
            key="exp_note",
        )

    if not st.button(
        "✅ 確認新增", use_container_width=True, type="primary", key="exp_submit"
    ):
        return False

    # 驗證
    try:
        amount_decimal = Decimal(str(amount_input))
    except InvalidOperation:
        st.error("❌ 金額格式錯誤。")
        return False

    if amount_decimal <= 0:
        st.error("❌ 金額必須大於 0。")
        return False

    new_id = add_expense(
        user_id=user_id,
        amount=amount_decimal,
        category_id=selected_cat_id,
        recorded_at=datetime.now(timezone.utc),
        note=note.strip() or None,
    )
    if new_id:
        logger.info("新增消費成功 ─ id=%s  amount=%s", new_id, amount_decimal)
        for k in ("exp_amount", "exp_note"):
            st.session_state.pop(k, None)
        return True

    st.error("❌ 新增失敗，請稍後再試。")
    return False


def _render_today_list(expenses: list[Expense], user_id: str) -> None:
    """今日明細列表（含二次確認刪除）。"""
    st.markdown(
        '<div style=\'font-size:0.65rem;font-family:"DM Mono",monospace;'
        "color:#8b85a8;text-transform:uppercase;letter-spacing:0.10em;"
        "margin-bottom:0.8rem'>▸ 今日明細</div>",
        unsafe_allow_html=True,
    )
    if not expenses:
        st.markdown(
            '<div class="exp-empty"><div class="empty-icon">📭</div>'
            '<div class="empty-text">今日尚無消費記錄<br>'
            '<span style="font-size:0.75rem">點擊左側表單新增第一筆！</span>'
            "</div></div>",
            unsafe_allow_html=True,
        )
        return

    for exp in expenses:
        col_info, col_del = st.columns([9, 1])
        with col_info:
            st.markdown(_expense_list_item_html(exp), unsafe_allow_html=True)
        with col_del:
            confirm_key = f"del_confirm_{exp.id}"
            if st.session_state.get(confirm_key):
                if st.button("✓", key=f"del_ok_{exp.id}", help="確認刪除"):
                    if soft_delete_expense(user_id,exp.id):
                        st.session_state.pop(confirm_key, None)
                        st.toast("已刪除此筆記錄", icon="🗑️")
                        st.rerun()
            else:
                if st.button("🗑️", key=f"del_{exp.id}", help="刪除此筆"):
                    st.session_state[confirm_key] = True
                    st.rerun()


# ③ 所有子函式簽名更新，以 _tab_today 為例：
def _tab_today(categories: list[Category], user_id: str) -> None:
    summary = get_today_summary(user_id)  # ← 帶入 user_id
    _render_kpi_cards(summary)
    _render_budget_banner(summary)

    col_form, col_list = st.columns([1, 1.2])
    with col_form:
        if _render_add_form(categories, user_id):  # ← 帶入 user_id
            st.toast("✅ 已新增！", icon="💰")
            st.rerun()
    with col_list:
        _render_today_list(summary.expenses, user_id)


# ─────────────────────────────────────────────────────────────────────────────
#  Tab 2｜歷史查詢（F-04）
# ─────────────────────────────────────────────────────────────────────────────


def _render_edit_form(exp: Expense, categories: list[Category], user_id: str) -> bool:
    """
    展開式編輯表單，回傳 True 表示儲存成功。
    嵌入在 st.expander 內呼叫。
    """
    edit_key = f"edit_{exp.id}"

    # 金額
    new_amount = st.number_input(
        "金額（NT$）",
        min_value=0.01,
        max_value=9_999_999.0,
        value=float(exp.amount),
        step=1.0,
        format="%.0f",
        key=f"{edit_key}_amount",
    )

    # 類別
    cat_ids = [c.id for c in categories]
    cat_labels = [f"{c.icon} {c.name}" for c in categories]
    current_idx = cat_ids.index(exp.category_id) if exp.category_id in cat_ids else 0
    new_cat_label = st.selectbox(
        "類別",
        options=cat_labels,
        index=current_idx,
        key=f"{edit_key}_cat",
    )
    new_cat_id = cat_ids[cat_labels.index(new_cat_label)]

    # 時間
    recorded_local = exp.recorded_at.replace(tzinfo=timezone.utc).astimezone(
        tz=None  # 轉換為 server local time
    )
    new_date = st.date_input(
        "消費日期",
        value=recorded_local.date(),
        key=f"{edit_key}_date",
    )
    new_time = st.time_input(
        "消費時間",
        value=recorded_local.time(),
        key=f"{edit_key}_time",
        step=60,
    )

    # 備註
    new_note = st.text_input(
        "備註（最多 200 字）",
        value=exp.note or "",
        max_chars=200,
        key=f"{edit_key}_note",
    )

    col_save, col_cancel = st.columns(2)
    with col_save:
        if st.button(
            "💾 儲存", key=f"{edit_key}_save", use_container_width=True, type="primary"
        ):
            try:
                amount_dec = Decimal(str(new_amount))
            except InvalidOperation:
                st.error("❌ 金額格式錯誤")
                return False

            if amount_dec <= 0:
                st.error("❌ 金額必須大於 0")
                return False

            # 組合新 recorded_at（local → UTC）
            new_recorded_local = datetime.combine(new_date, new_time)
            new_recorded_utc = new_recorded_local.astimezone(timezone.utc)

            if new_recorded_utc > datetime.now(timezone.utc):
                st.error("❌ 不允許設定未來時間")
                return False

            ok = update_expense(
                user_id=user_id,
                expense_id=exp.id,
                amount=amount_dec,
                category_id=new_cat_id,
                recorded_at=new_recorded_utc,
                note=new_note.strip() or None,
            )
            if ok:
                logger.info("更新消費成功 ─ id=%s", exp.id)
                return True
            st.error("❌ 儲存失敗，請稍後再試。")
    with col_cancel:
        if st.button("✕ 取消", key=f"{edit_key}_cancel", use_container_width=True):
            st.rerun()

    return False


def _render_history_stats(expenses: list[Expense]) -> None:
    """顯示篩選結果的摘要統計 chip。"""
    if not expenses:
        return
    total = sum(e.amount for e in expenses)
    count = len(expenses)
    avg = total / count
    st.markdown(
        f"""
        <div class="hist-stat-row">
          <div class="hist-stat-chip">📋 共 {count} 筆</div>
          <div class="hist-stat-chip">💰 合計 NT$ {float(total):,.0f}</div>
          <div class="hist-stat-chip">📊 平均 NT$ {float(avg):,.0f}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _tab_history(categories: list[Category], user_id: str) -> None:
    """Tab 2 主渲染函式 — 歷史記錄查詢（F-04）。"""

    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    # ── 篩選工具列（用 container border=True 取代破損的 div 包法）──
    with st.container(border=True):
        st.markdown(
            '<div class="hist-section-label">🔍 篩選條件</div>',
            unsafe_allow_html=True,
        )
        col_d1, col_d2, col_cat, col_reset = st.columns([2, 2, 2, 1])

        with col_d1:
            start_date: date = st.date_input(
                "開始日期",
                value=st.session_state.get("hist_start", week_start),
                max_value=today,
                key="hist_start",
            )
        with col_d2:
            end_date: date = st.date_input(
                "結束日期",
                value=st.session_state.get("hist_end", today),
                min_value=start_date,
                max_value=today,
                key="hist_end",
            )
        with col_cat:
            cat_options = ["全部類別"] + [f"{c.icon} {c.name}" for c in categories]
            cat_filter: str = st.selectbox(
                "類別篩選",
                options=cat_options,
                key="hist_cat_filter",
            )
        with col_reset:
            # 對齊 label 高度
            st.markdown("<div style='height:1.9rem'></div>", unsafe_allow_html=True)
            if st.button(
                "↺ 重設", help="重設為本週", use_container_width=True, key="hist_reset"
            ):
                for k in ("hist_start", "hist_end", "hist_cat_filter"):
                    st.session_state.pop(k, None)
                st.rerun()

    # ── 驗證日期區間 ──────────────────────────────────────────────
    if start_date > end_date:
        st.error("❌ 開始日期不可晚於結束日期")
        return

    # ── 解析類別篩選 ──────────────────────────────────────────────
    selected_cat_id: Optional[str] = None
    if cat_filter != "全部類別":
        matched = [c for c in categories if f"{c.icon} {c.name}" == cat_filter]
        if matched:
            selected_cat_id = matched[0].id

    # ── 查詢資料 ──────────────────────────────────────────────────
    expenses = get_expenses(
        user_id=user_id,
        start_date=start_date,
        end_date=end_date,
        category_id=selected_cat_id,
    )

    logger.info(
        "歷史查詢 ─ start=%s  end=%s  cat=%s  count=%d",
        start_date,
        end_date,
        selected_cat_id,
        len(expenses),
    )

    # ── 統計摘要 ──────────────────────────────────────────────────
    _render_history_stats(expenses)

    # ── 結果列表 ──────────────────────────────────────────────────
    if not expenses:
        st.markdown(
            '<div class="exp-empty"><div class="empty-icon">🔍</div>'
            '<div class="empty-text">此條件下無消費記錄</div></div>',
            unsafe_allow_html=True,
        )
        return

    for exp in expenses:
        exp_date_str = exp.recorded_at.strftime("%m/%d")
        exp_time_str = exp.recorded_at.strftime("%H:%M")
        label = (
            f"{exp.category_icon} {exp.category_name}｜"
            f"NT$ {float(exp.amount):,.0f}｜"
            f"{exp_date_str} {exp_time_str}"
        )
        with st.expander(label, expanded=False):
            col_detail, col_actions = st.columns([3, 1])
            with col_detail:
                st.markdown(
                    f"**類別**：{exp.category_icon} {exp.category_name}  \n"
                    f"**金額**：NT$ {float(exp.amount):,.0f}  \n"
                    f"**時間**：{exp.recorded_at.strftime('%Y-%m-%d %H:%M')}  \n"
                    f"**備註**：{exp.note or '（無）'}"
                )
            with col_actions:
                edit_flag = f"show_edit_{exp.id}"
                if st.button(
                    "✏️ 編輯", key=f"edit_btn_{exp.id}", use_container_width=True
                ):
                    st.session_state[edit_flag] = not st.session_state.get(
                        edit_flag, False
                    )
                    st.rerun()

                del_flag = f"hist_del_{exp.id}"
                if st.session_state.get(del_flag):
                    if st.button(
                        "⚠️ 確認刪除",
                        key=f"hist_del_ok_{exp.id}",
                        use_container_width=True,
                        type="primary",
                    ):
                        if soft_delete_expense(exp.id):
                            st.session_state.pop(del_flag, None)
                            st.toast("已刪除", icon="🗑️")
                            st.rerun()
                else:
                    if st.button(
                        "🗑️ 刪除", key=f"hist_del_{exp.id}_btn", use_container_width=True
                    ):
                        st.session_state[del_flag] = True
                        st.rerun()

            if st.session_state.get(edit_flag, False):
                st.divider()
                if _render_edit_form(exp, categories):
                    st.session_state.pop(edit_flag, None)
                    st.toast("✅ 已更新！", icon="💾")
                    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  頁面主函式
# ─────────────────────────────────────────────────────────────────────────────


# ② 在 show() 開頭取得 user_id（必須已登入才能到此頁）
def show() -> None:
    # ── 取得 user_id（優先從 session，沒有則即時查詢並補存）──────
    user_id: Optional[int] = st.session_state.get("user_id")

    if not user_id:
        username: str = st.session_state.get("username", "")
        if username:
            user_id = get_user_id(username)
            if user_id:
                # 補存到 session，後續不再重查
                st.session_state["user_id"] = user_id
                logger.info("user_id 補查成功 ─ user=%s  id=%s", username, user_id)

    if not user_id:
        st.error("❌ 無法取得使用者資訊，請重新登入。")
        logger.error("show() 缺少 user_id ─ session=%s", dict(st.session_state))
        return

    logger.info(
        "渲染消費記錄頁 ─ user=%s  id=%s", st.session_state.get("username"), user_id
    )
    st.markdown(_PAGE_CSS, unsafe_allow_html=True)
    st.markdown(_MOBILE_CSS, unsafe_allow_html=True)

    categories = get_all_categories(user_id)

    tab_today, tab_history = st.tabs(["📅 今日總覽", "📋 歷史記錄"])
    with tab_today:
        _tab_today(categories, user_id)
    with tab_history:
        _tab_history(categories, user_id)

    logger.info("消費記錄頁渲染完成")
