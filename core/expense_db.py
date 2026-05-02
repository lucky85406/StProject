# core/expense_db.py
"""
每日消費記錄 — 資料存取層（Data Access Layer）
所有 Supabase 查詢集中於此，頁面層只呼叫此模組的函式。
v2：所有查詢依 user_id（UUID）隔離，支援多使用者。
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
# 資料類別
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
# 內部 Helper
# ──────────────────────────────────────────────


def _row_to_expense(row: dict) -> Expense:
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


# ──────────────────────────────────────────────
# 類別管理（F-02）
# ──────────────────────────────────────────────


def get_all_categories(user_id: str) -> list[Category]:
    """
    取得全域預設類別（is_default=TRUE, user_id IS NULL）
    + 指定使用者的自訂類別，依 sort_order 排序。
    """
    try:
        client = get_client()
        # 全域預設
        default_res = (
            client.table("categories")
            .select("id, name, icon, is_default, sort_order")
            .is_("user_id", "null")
            .eq("is_default", True)
            .order("sort_order")
            .execute()
        )
        # 使用者自訂
        custom_res = (
            client.table("categories")
            .select("id, name, icon, is_default, sort_order")
            .eq("user_id", user_id)
            .order("sort_order")
            .execute()
        )
        rows = (default_res.data or []) + (custom_res.data or [])
        return [
            Category(
                id=r["id"],
                name=r["name"],
                icon=r["icon"],
                is_default=r["is_default"],
                sort_order=r["sort_order"],
            )
            for r in rows
        ]
    except Exception as e:
        logger.error("get_all_categories 失敗 ─ user=%s  error=%s", user_id, e)
        return []


def add_category(user_id: str, name: str, icon: str) -> bool:
    """新增使用者自訂類別（名稱重複時回傳 False）。"""
    name = name.strip()
    if not name or len(name) > 20:
        logger.warning("add_category 名稱無效 ─ name=%r", name)
        return False
    try:
        client = get_client()
        client.table("categories").insert(
            {"name": name, "icon": icon, "is_default": False, "user_id": user_id}
        ).execute()
        logger.info("add_category 成功 ─ user=%s  name=%s", user_id, name)
        return True
    except Exception as e:
        logger.warning("add_category 失敗 ─ name=%s  error=%s", name, e)
        return False


def delete_category(user_id: str, category_id: str) -> bool:
    """刪除使用者自訂類別（is_default=TRUE 或非本人類別不可刪）。"""
    try:
        client = get_client()
        check = (
            client.table("categories")
            .select("is_default, user_id")
            .eq("id", category_id)
            .single()
            .execute()
        )
        if not check.data:
            return False
        if check.data["is_default"] or check.data.get("user_id") != user_id:
            logger.warning(
                "delete_category 拒絕：預設類別或非本人 ─ id=%s  user=%s",
                category_id,
                user_id,
            )
            return False
        client.table("categories").delete().eq("id", category_id).execute()
        logger.info("delete_category 成功 ─ id=%s  user=%s", category_id, user_id)
        return True
    except Exception as e:
        logger.error("delete_category 失敗 ─ id=%s  error=%s", category_id, e)
        return False


# ──────────────────────────────────────────────
# 預算設定（F-05）
# ──────────────────────────────────────────────


def get_budget(user_id: str) -> Optional[BudgetSetting]:
    """取得指定使用者目前啟用的預算設定。"""
    try:
        client = get_client()
        result = (
            client.table("budget_settings")
            .select("id, daily_limit, is_active, updated_at")
            .eq("user_id", user_id)
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
        logger.error("get_budget 失敗 ─ user=%s  error=%s", user_id, e)
        return None


def update_budget(user_id: str, daily_limit: Decimal, is_active: bool = True) -> bool:
    """更新指定使用者的預算設定（upsert 語意）。"""
    if daily_limit <= 0:
        logger.warning("update_budget 金額無效 ─ daily_limit=%s", daily_limit)
        return False
    try:
        client = get_client()
        budget = get_budget(user_id)
        if budget:
            client.table("budget_settings").update(
                {"daily_limit": float(daily_limit), "is_active": is_active}
            ).eq("id", budget.id).execute()
        else:
            client.table("budget_settings").insert(
                {
                    "daily_limit": float(daily_limit),
                    "is_active": is_active,
                    "user_id": user_id,
                }
            ).execute()
        logger.info("update_budget 成功 ─ user=%s  limit=%s", user_id, daily_limit)
        return True
    except Exception as e:
        logger.error("update_budget 失敗 ─ user=%s  error=%s", user_id, e)
        return False


# ──────────────────────────────────────────────
# 消費記錄 CRUD（F-01, F-03, F-04）
# ──────────────────────────────────────────────


def add_expense(
    user_id: str,
    amount: Decimal,
    category_id: str,
    recorded_at: Optional[datetime] = None,
    note: Optional[str] = None,
) -> Optional[str]:
    """新增一筆消費記錄，回傳新建 id，失敗回傳 None。"""
    if amount <= 0:
        logger.warning("add_expense 金額無效 ─ amount=%s", amount)
        return None
    now = datetime.now(timezone.utc)
    if recorded_at and recorded_at.replace(tzinfo=timezone.utc) > now:
        logger.warning("add_expense 拒絕未來時間 ─ recorded_at=%s", recorded_at)
        return None
    note_clean: Optional[str] = note.strip()[:200] if note and note.strip() else None
    try:
        client = get_client()
        payload: dict = {
            "user_id": user_id,
            "amount": float(amount),
            "category_id": category_id,
            "note": note_clean,
        }
        if recorded_at:
            payload["recorded_at"] = recorded_at.isoformat()
        result = client.table("expenses").insert(payload).execute()
        new_id: str = result.data[0]["id"]
        logger.info("add_expense 成功 ─ user=%s  id=%s", user_id, new_id)
        return new_id
    except Exception as e:
        logger.error("add_expense 失敗 ─ user=%s  error=%s", user_id, e)
        return None


def get_today_summary(user_id: str) -> TodaySummary:
    """取得指定使用者今日消費總覽（F-03）。"""
    today_str = date.today().isoformat()
    try:
        client = get_client()
        result = (
            client.table("expenses")
            .select("*, categories(name, icon)")
            .eq("user_id", user_id)
            .gte("recorded_at", f"{today_str}T00:00:00")
            .lte("recorded_at", f"{today_str}T23:59:59.999999")
            .eq("is_deleted", False)
            .order("recorded_at", desc=True)
            .execute()
        )
        expenses = [_row_to_expense(row) for row in (result.data or [])]
        total = sum(e.amount for e in expenses)
        budget = get_budget(user_id)
        is_over = budget is not None and budget.is_active and total > budget.daily_limit
        return TodaySummary(
            total=total,
            expenses=expenses,
            is_over_budget=is_over,
            budget_limit=budget.daily_limit if budget else None,
        )
    except Exception as e:
        logger.error("get_today_summary 失敗 ─ user=%s  error=%s", user_id, e)
        return TodaySummary(
            total=Decimal("0"), expenses=[], is_over_budget=False, budget_limit=None
        )


def get_expenses(
    user_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    category_id: Optional[str] = None,
) -> list[Expense]:
    """查詢指定使用者的消費列表（F-04），支援日期區間與類別篩選。"""
    if start_date is None:
        start_date = date.today()
    if end_date is None:
        end_date = date.today()
    try:
        client = get_client()
        query = (
            client.table("expenses")
            .select("*, categories(name, icon)")
            .eq("user_id", user_id)
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
        logger.error("get_expenses 失敗 ─ user=%s  error=%s", user_id, e)
        return []


def get_expense_by_id(user_id: str, expense_id: str) -> Optional[Expense]:
    """取得單筆消費詳情（確保屬於該使用者）。"""
    try:
        client = get_client()
        result = (
            client.table("expenses")
            .select("*, categories(name, icon)")
            .eq("id", expense_id)
            .eq("user_id", user_id)  # ← 防止跨使用者存取
            .eq("is_deleted", False)
            .single()
            .execute()
        )
        return _row_to_expense(result.data) if result.data else None
    except Exception as e:
        logger.error("get_expense_by_id 失敗 ─ id=%s  error=%s", expense_id, e)
        return None


def update_expense(
    user_id: str,
    expense_id: str,
    amount: Optional[Decimal] = None,
    category_id: Optional[str] = None,
    recorded_at: Optional[datetime] = None,
    note: Optional[str] = None,
) -> bool:
    """修改消費記錄（PATCH 語意，僅更新有傳入的欄位）。"""
    payload: dict = {}
    if amount is not None:
        if amount <= 0:
            return False
        payload["amount"] = float(amount)
    if category_id is not None:
        payload["category_id"] = category_id
    if recorded_at is not None:
        if recorded_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
            return False
        payload["recorded_at"] = recorded_at.isoformat()
    if note is not None:
        payload["note"] = note.strip()[:200] if note.strip() else None
    if not payload:
        return False
    try:
        client = get_client()
        client.table("expenses").update(payload).eq("id", expense_id).eq(
            "user_id", user_id
        ).execute()
        logger.info("update_expense 成功 ─ user=%s  id=%s", user_id, expense_id)
        return True
    except Exception as e:
        logger.error("update_expense 失敗 ─ id=%s  error=%s", expense_id, e)
        return False


def soft_delete_expense(user_id: str, expense_id: str) -> bool:
    """軟刪除消費記錄（確保屬於該使用者才可刪除）。"""
    try:
        client = get_client()
        client.table("expenses").update({"is_deleted": True}).eq("id", expense_id).eq(
            "user_id", user_id
        ).execute()  # ← 防止跨使用者刪除
        logger.info("soft_delete_expense 成功 ─ user=%s  id=%s", user_id, expense_id)
        return True
    except Exception as e:
        logger.error("soft_delete_expense 失敗 ─ id=%s  error=%s", expense_id, e)
        return False
