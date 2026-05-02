# core/expense_db.py
"""
每日消費記錄 — 資料存取層（Data Access Layer）
所有 Supabase 查詢集中於此，頁面層只呼叫此模組的函式。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from core.db import get_client

logger = logging.getLogger("core.expense_db")


# ──────────────────────────────────────────────
# 資料類別（純 Python，不依賴 ORM）
# ──────────────────────────────────────────────


@dataclass
class Category:
    id: str
    name: str
    icon: str
    is_default: bool
    sort_order: int


@dataclass
class Expense:
    id: str
    amount: Decimal
    category_id: str
    category_name: str
    category_icon: str
    recorded_at: datetime
    note: Optional[str]
    created_at: datetime


@dataclass
class BudgetSetting:
    id: str
    daily_limit: Decimal
    is_active: bool
    updated_at: datetime


@dataclass
class TodaySummary:
    total: Decimal
    expenses: list[Expense]
    is_over_budget: bool
    budget_limit: Optional[Decimal]


# ──────────────────────────────────────────────
# 類別管理（F-02）
# ──────────────────────────────────────────────


def get_all_categories() -> list[Category]:
    """取得所有類別，依 sort_order 排序。"""
    try:
        client = get_client()
        result = (
            client.table("categories")
            .select("id, name, icon, is_default, sort_order")
            .order("sort_order")
            .execute()
        )
        return [
            Category(
                id=row["id"],
                name=row["name"],
                icon=row["icon"],
                is_default=row["is_default"],
                sort_order=row["sort_order"],
            )
            for row in (result.data or [])
        ]
    except Exception as e:
        logger.error("get_all_categories 失敗 ─ error=%s", e)
        return []


def add_category(name: str, icon: str) -> bool:
    """新增自訂類別。名稱重複時回傳 False。"""
    name = name.strip()
    if not name or len(name) > 20:
        logger.warning("add_category 名稱無效 ─ name=%r", name)
        return False
    try:
        client = get_client()
        client.table("categories").insert(
            {"name": name, "icon": icon, "is_default": False}
        ).execute()
        logger.info("add_category 成功 ─ name=%s  icon=%s", name, icon)
        return True
    except Exception as e:
        logger.warning("add_category 失敗（可能重複） ─ name=%s  error=%s", name, e)
        return False


def delete_category(category_id: str) -> bool:
    """刪除自訂類別（is_default=TRUE 的類別不可刪除）。"""
    try:
        client = get_client()
        # 確認非預設類別才允許刪除
        check = (
            client.table("categories")
            .select("is_default")
            .eq("id", category_id)
            .single()
            .execute()
        )
        if check.data and check.data["is_default"]:
            logger.warning("delete_category 拒絕刪除預設類別 ─ id=%s", category_id)
            return False

        client.table("categories").delete().eq("id", category_id).execute()
        logger.info("delete_category 成功 ─ id=%s", category_id)
        return True
    except Exception as e:
        logger.error("delete_category 失敗 ─ id=%s  error=%s", category_id, e)
        return False


# ──────────────────────────────────────────────
# 預算設定（F-05）
# ──────────────────────────────────────────────


def get_budget() -> Optional[BudgetSetting]:
    """取得目前啟用的預算設定（取第一筆 is_active=TRUE）。"""
    try:
        client = get_client()
        result = (
            client.table("budget_settings")
            .select("id, daily_limit, is_active, updated_at")
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None
        row = result.data[0]
        return BudgetSetting(
            id=row["id"],
            daily_limit=Decimal(str(row["daily_limit"])),
            is_active=row["is_active"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
    except Exception as e:
        logger.error("get_budget 失敗 ─ error=%s", e)
        return None


def update_budget(daily_limit: Decimal, is_active: bool = True) -> bool:
    """更新預算設定（upsert：存在則更新，不存在則新增）。"""
    if daily_limit <= 0:
        logger.warning("update_budget 金額無效 ─ daily_limit=%s", daily_limit)
        return False
    try:
        client = get_client()
        budget = get_budget()
        if budget:
            client.table("budget_settings").update(
                {"daily_limit": float(daily_limit), "is_active": is_active}
            ).eq("id", budget.id).execute()
        else:
            client.table("budget_settings").insert(
                {"daily_limit": float(daily_limit), "is_active": is_active}
            ).execute()
        logger.info("update_budget 成功 ─ limit=%s  active=%s", daily_limit, is_active)
        return True
    except Exception as e:
        logger.error("update_budget 失敗 ─ error=%s", e)
        return False


# ──────────────────────────────────────────────
# 消費記錄 CRUD（F-01, F-04）
# ──────────────────────────────────────────────


def _row_to_expense(row: dict) -> Expense:
    """將 Supabase 原始 row 轉為 Expense dataclass。"""
    cat = row.get("categories") or {}
    return Expense(
        id=row["id"],
        amount=Decimal(str(row["amount"])),
        category_id=row["category_id"],
        category_name=cat.get("name", ""),
        category_icon=cat.get("icon", ""),
        recorded_at=datetime.fromisoformat(row["recorded_at"]),
        note=row.get("note"),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def add_expense(
    amount: Decimal,
    category_id: str,
    recorded_at: Optional[datetime] = None,
    note: Optional[str] = None,
) -> Optional[str]:
    """
    新增一筆消費記錄。
    回傳新建記錄的 id（str），失敗回傳 None。
    """
    if amount <= 0:
        logger.warning("add_expense 金額無效 ─ amount=%s", amount)
        return None

    # 不允許未來時間
    now = datetime.now(timezone.utc)
    if recorded_at and recorded_at.replace(tzinfo=timezone.utc) > now:
        logger.warning("add_expense 拒絕未來時間 ─ recorded_at=%s", recorded_at)
        return None

    note_clean: Optional[str] = note.strip()[:200] if note and note.strip() else None

    try:
        client = get_client()
        payload: dict = {
            "amount": float(amount),
            "category_id": category_id,
            "note": note_clean,
        }
        if recorded_at:
            payload["recorded_at"] = recorded_at.isoformat()

        result = client.table("expenses").insert(payload).execute()
        new_id: str = result.data[0]["id"]
        logger.info("add_expense 成功 ─ id=%s  amount=%s", new_id, amount)
        return new_id
    except Exception as e:
        logger.error("add_expense 失敗 ─ error=%s", e)
        return None


def get_today_summary() -> TodaySummary:
    """
    取得今日消費總覽（F-03）：
    - 今日消費列表（recorded_at 日期 = 今天，台灣時區）
    - 今日加總
    - 是否超出預算
    """
    today_str = date.today().isoformat()  # "YYYY-MM-DD"
    try:
        client = get_client()
        result = (
            client.table("expenses")
            .select("*, categories(name, icon)")
            .gte("recorded_at", f"{today_str}T00:00:00")
            .lte("recorded_at", f"{today_str}T23:59:59.999999")
            .eq("is_deleted", False)
            .order("recorded_at", desc=True)
            .execute()
        )
        expenses = [_row_to_expense(row) for row in (result.data or [])]
        total = sum(e.amount for e in expenses)

        budget = get_budget()
        is_over = budget is not None and budget.is_active and total > budget.daily_limit
        return TodaySummary(
            total=total,
            expenses=expenses,
            is_over_budget=is_over,
            budget_limit=budget.daily_limit if budget else None,
        )
    except Exception as e:
        logger.error("get_today_summary 失敗 ─ error=%s", e)
        return TodaySummary(
            total=Decimal("0"),
            expenses=[],
            is_over_budget=False,
            budget_limit=None,
        )


def get_expenses(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category_id: Optional[str] = None,
) -> list[Expense]:
    """
    查詢消費列表（F-04），支援日期區間與類別篩選。
    未傳入日期時預設查詢本週（週一至今）。
    """
    if start_date is None:
        today = date.today()
        start_date = today  # 預設今天，頁面層可覆蓋
    if end_date is None:
        end_date = date.today()

    try:
        client = get_client()
        query = (
            client.table("expenses")
            .select("*, categories(name, icon)")
            .gte("recorded_at", f"{start_date.isoformat()}T00:00:00")
            .lte("recorded_at", f"{end_date.isoformat()}T23:59:59.999999")
            .eq("is_deleted", False)
            .order("recorded_at", desc=True)
        )
        if category_id:
            query = query.eq("category_id", category_id)

        result = query.execute()
        return [_row_to_expense(row) for row in (result.data or [])]
    except Exception as e:
        logger.error("get_expenses 失敗 ─ error=%s", e)
        return []


def get_expense_by_id(expense_id: str) -> Optional[Expense]:
    """取得單筆消費詳情。"""
    try:
        client = get_client()
        result = (
            client.table("expenses")
            .select("*, categories(name, icon)")
            .eq("id", expense_id)
            .eq("is_deleted", False)
            .single()
            .execute()
        )
        return _row_to_expense(result.data) if result.data else None
    except Exception as e:
        logger.error("get_expense_by_id 失敗 ─ id=%s  error=%s", expense_id, e)
        return None


def update_expense(
    expense_id: str,
    amount: Optional[Decimal] = None,
    category_id: Optional[str] = None,
    recorded_at: Optional[datetime] = None,
    note: Optional[str] = None,
) -> bool:
    """修改消費記錄（PATCH 語意：只更新有傳入的欄位）。"""
    payload: dict = {}
    if amount is not None:
        if amount <= 0:
            return False
        payload["amount"] = float(amount)
    if category_id is not None:
        payload["category_id"] = category_id
    if recorded_at is not None:
        now = datetime.now(timezone.utc)
        if recorded_at.replace(tzinfo=timezone.utc) > now:
            return False
        payload["recorded_at"] = recorded_at.isoformat()
    if note is not None:
        payload["note"] = note.strip()[:200] if note.strip() else None

    if not payload:
        return False

    try:
        client = get_client()
        client.table("expenses").update(payload).eq("id", expense_id).execute()
        logger.info("update_expense 成功 ─ id=%s  fields=%s", expense_id, list(payload))
        return True
    except Exception as e:
        logger.error("update_expense 失敗 ─ id=%s  error=%s", expense_id, e)
        return False


def soft_delete_expense(expense_id: str) -> bool:
    """軟刪除消費記錄（is_deleted = TRUE，資料保留於 DB）。"""
    try:
        client = get_client()
        client.table("expenses").update({"is_deleted": True}).eq(
            "id", expense_id
        ).execute()
        logger.info("soft_delete_expense 成功 ─ id=%s", expense_id)
        return True
    except Exception as e:
        logger.error("soft_delete_expense 失敗 ─ id=%s  error=%s", expense_id, e)
        return False
