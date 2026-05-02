# 🧩 core/ — 核心業務邏輯模組

本目錄包含 StProject 所有共用核心邏輯，涵蓋資料庫連線、身份驗證、Session 管理、TOTP、QR 登入與消費記錄資料存取層。

> **設計原則**：所有模組均採用標準 Python `logging`，**不直接依賴 Streamlit**，可獨立進行單元測試。

---

## 目錄結構

```
core/
├── auth.py           # Auth 公開介面（re-export session_store）
├── db.py             # Supabase 連線工廠（lru_cache 單例）
├── expense_db.py     # 消費記錄 DAL（v2：user_id 多使用者隔離）
├── network.py        # 網路工具（取得本機 IP）
├── qr_login.py       # QR Code 圖片產生與確認 URL 建構
├── qr_store.py       # QR Token 狀態機（JSON 檔案儲存）
├── session_store.py  # 登入 Session 建立 / 驗證 / 刪除
├── totp.py           # Google Authenticator TOTP 工具（RFC 6238）
└── users.py          # 使用者帳號驗證與管理
```

---

## 🔌 db.py — Supabase 連線工廠

Supabase 客戶端的單例工廠，整個 App 生命週期只初始化一次。

```python
from core.db import get_client

client = get_client()  # 回傳快取的 supabase.Client
```

**實作細節**：
- 使用 `@lru_cache(maxsize=1)` 確保連線不重複建立
- 憑證從 `st.secrets["supabase"]` 讀取（`.streamlit/secrets.toml`）
- 使用 **service_role** key，繞過 Row Level Security（RLS），適合伺服器端操作
- Supabase Python Client 為執行緒安全，在 Streamlit 多執行緒環境下可正常運作

### 必要 Secrets 設定

```toml
# .streamlit/secrets.toml
[supabase]
url = "https://xxxxxxxxxxxx.supabase.co"
service_key = "eyJ..."
```

---

## 👤 users.py — 使用者帳號管理

提供所有帳號相關操作，對接 Supabase `users` 資料表。

### 主要函式

| 函式 | 回傳值 | 說明 |
|------|--------|------|
| `verify_login(username, password, totp_code)` | `tuple[bool, LoginReason]` | 統一登入驗證入口 |
| `verify_password(username, password)` | `bool` | 僅驗證密碼（bcrypt checkpw） |
| `user_exists(username)` | `bool` | 確認使用者是否存在（QR 登入用） |
| `get_user_id(username)` | `str \| None` | 取得使用者 UUID（消費記錄隔離用） |
| `create_user(username, password)` | `bool` | 新增使用者，TOTP 預設停用 |
| `change_password(username, old_pw, new_pw)` | `bool` | 修改密碼（驗證舊密碼後 bcrypt 重新 Hash） |
| `get_totp_info(username)` | `tuple[bool, str \| None]` | 取得 `(totp_enabled, totp_secret)` |
| `save_totp_secret(username, secret)` | `bool` | 儲存 TOTP 秘鑰並啟用 |
| `disable_totp(username)` | `bool` | 停用 TOTP，清除 secret |

### 登入驗證流程

```
verify_login(username, password, totp_code)
    ├─ Step 1: bcrypt.checkpw(password, stored_hash)
    │       └─ 失敗 → return (False, "wrong_password")
    ├─ Step 2: 使用者存在確認
    │       └─ 不存在 → return (False, "not_found")
    ├─ Step 3: totp_enabled 檢查
    │       ├─ True + totp_code 為空 → return (False, "totp_required")
    │       ├─ True + 驗證失敗 → return (False, "wrong_totp")
    │       └─ False → 跳過 TOTP 驗證
    └─ 成功 → return (True, "ok")
```

### LoginReason 型別

```python
LoginReason = Literal["ok", "wrong_password", "totp_required", "wrong_totp", "not_found"]
```

### Supabase 資料表：`users`

| 欄位 | 型別 | 說明 |
|------|------|------|
| `id` | uuid | 主鍵（`gen_random_uuid()`） |
| `username` | text | 唯一帳號名稱 |
| `password` | text | bcrypt hash（rounds=12） |
| `totp_enabled` | bool | 是否已啟用 TOTP（預設 False） |
| `totp_secret` | text | Base32 TOTP 秘鑰（可為 NULL） |
| `created_at` | timestamptz | 建立時間 |

> **安全設計**：登入失敗時一律回傳模糊錯誤訊息，防止帳號枚舉攻擊（Account Enumeration）。

---

## 🔑 session_store.py — Session 管理

管理登入後的使用者 Session，透過 URL Query Param `?sid=` 保留登入狀態，**無需 Cookie**。

### 主要函式

| 函式 | 回傳值 | 說明 |
|------|--------|------|
| `create_session(username)` | `str` | 建立 Session，回傳 UUID sid |
| `verify_session(sid)` | `str \| None` | 驗證 sid 是否有效，回傳 username 或 None |
| `delete_session(sid)` | `None` | 刪除 Session（登出用） |

### Session 恢復機制

`app.py` 啟動時自動從 `st.query_params["sid"]` 讀取並呼叫 `verify_session()`，實現頁面重整後保持登入狀態。

### auth.py — 公開介面

`core/auth.py` 直接 re-export `session_store` 的函式，統一 import 路徑：

```python
from core.auth import create_session, verify_session, delete_session
```

---

## 🛡️ totp.py — Google Authenticator 工具

實作 RFC 6238 TOTP，與 Google Authenticator 完全相容。

### 主要函式

| 函式 | 說明 |
|------|------|
| `generate_secret()` | 產生 32 字元 Base32 隨機秘鑰 |
| `get_provisioning_uri(secret, username)` | 產生 `otpauth://totp/...` URI |
| `generate_setup_qr_png(secret, username)` | 產生供掃描的 QR Code PNG（bytes） |
| `verify_code(secret, code)` | 驗證 6 位數碼（含 ±30 秒容差） |

### TOTP Enrollment 強制閘門

首次登入（密碼正確但 `totp_enabled=False`）時，`app.py` 會**強制顯示 TOTP 設定頁面**，在使用者完成 Google Authenticator 設定並驗證成功前，不會建立 Session。此機制同時適用於帳號密碼登入和 QR Code 登入兩種方式。

---

## 📱 qr_login.py — QR Code 圖片產生

負責 QR Code 登入的圖片渲染與確認 URL 建構。

### 主要函式

| 函式 | 說明 |
|------|------|
| `generate_qr_image(data)` | 將字串資料渲染為 QR Code PNG（bytes） |
| `build_confirm_url(token_id, username, base_url)` | 建構手機端掃碼確認的完整 URL |

---

## 🎫 qr_store.py — QR Token 狀態機

管理 QR Code 登入的 Token 生命週期，使用本機 JSON 檔案（`.qr_store.json`）儲存狀態。

### Token 狀態流程

```
create_qr_token()
    → status: "pending"
    → 手機掃碼
confirm_qr_token(token_id, username)
    → status: "confirmed"
    → 桌面輪詢偵測
consume_qr_token(token_id)
    → Token 消費（防重放攻擊）
    → 建立正式 Session
check_qr_token(token_id)
    → "pending" | "confirmed" | "expired"
```

### 主要函式

| 函式 | 回傳值 | 說明 |
|------|--------|------|
| `create_qr_token()` | `str` | 建立新 Token，回傳 token_id |
| `check_qr_token(token_id)` | `tuple[str, str \| None]` | 查詢狀態，回傳 `(status, confirmed_user)` |
| `confirm_qr_token(token_id, username)` | `bool` | 手機端確認，寫入 username |
| `consume_qr_token(token_id)` | `bool` | 消費 Token（建立 Session 前呼叫） |

### 輪詢機制

桌面端使用 `@st.fragment(run_every=3)` 每 3 秒自動呼叫 `check_qr_token()`，偵測到 `"confirmed"` 狀態後透過 `st.rerun(scope="app")` 執行整頁跳轉。

> ⚠️ **部署限制**：JSON 檔案儲存僅適合**單機部署**。多實例水平擴展時，應將 Token 儲存改為 Supabase 資料表或 Redis。

---

## 🌐 network.py — 網路工具

| 函式 | 說明 |
|------|------|
| `get_local_ip()` | 取得本機區域網路 IP（QR Code 確認 URL 建構用） |

---

## 💳 expense_db.py — 消費記錄資料存取層（v2）

> **v2 重大更新**：所有查詢依 `user_id`（UUID）隔離，支援多使用者各自獨立的消費記錄、類別與預算設定。

頁面層（`pages/daily_expense.py`）的所有 Supabase 操作均集中於此，實現關注點分離。

### 資料類別（dataclass）

| 類別 | 主要欄位 | 說明 |
|------|----------|------|
| `Category` | `id, name, icon, is_default, sort_order` | 消費類別 |
| `Expense` | `id, amount, category_id, category_name, category_icon, recorded_at, note, created_at` | 消費記錄 |
| `BudgetSetting` | `id, daily_limit, is_active, updated_at` | 預算設定 |
| `TodaySummary` | `total, expenses, is_over_budget, budget_limit` | 今日彙總（計算型，非資料庫實體） |

### 主要函式

**類別管理**

| 函式 | 說明 |
|------|------|
| `get_all_categories(user_id)` | 全域預設類別（`is_default=True, user_id IS NULL`）+ 使用者自訂類別，依 `sort_order` 排序 |
| `add_category(user_id, name, icon)` | 新增使用者自訂類別（名稱重複或超過 20 字時回傳 `False`） |
| `delete_category(user_id, category_id)` | 刪除類別（`is_default=True` 或非本人類別時拒絕） |

**消費記錄**

| 函式 | 說明 |
|------|------|
| `add_expense(user_id, amount, category_id, recorded_at, note)` | 新增消費記錄，回傳新建 `id`（`str \| None`） |
| `get_expenses_by_date(user_id, target_date)` | 取得指定日期的消費清單 |
| `delete_expense(user_id, expense_id)` | 刪除消費記錄（驗證 `user_id` 確保只能刪自己的資料） |

**預算設定**

| 函式 | 說明 |
|------|------|
| `get_budget(user_id)` | 取得當前有效預算設定，回傳 `BudgetSetting \| None` |
| `update_budget(user_id, daily_limit, is_active)` | 更新預算（upsert 語意，不存在時自動建立） |

### 防呆機制

- 金額 ≤ 0 時拒絕新增，記錄 `WARNING` log
- 不允許新增「未來時間」的消費記錄
- 備註超過 200 字時自動截斷並記錄 `WARNING`
- 刪除預設類別或他人類別時回傳 `False` 並記錄警告
- 類別名稱空字串或超過 20 字時拒絕新增

---

## 🏗️ 模組依賴關係

```
app.py
  ├─ core.auth           → core.session_store
  ├─ core.users          → core.db, core.totp
  ├─ core.qr_store       （無外部依賴）
  └─ core.qr_login       → core.network

pages/daily_expense.py
  └─ core.expense_db     → core.db

pages/settings.py
  ├─ core.users          → core.db, core.totp
  └─ core.session_store
```

---

## ⚠️ 注意事項

| 項目 | 說明 |
|------|------|
| `db.py` lru_cache | Supabase Python Client 為執行緒安全，Streamlit 多執行緒環境下可正常使用 |
| `qr_store.py` | JSON 檔案儲存僅適合單機部署；多機部署應改用 Supabase 或 Redis |
| `session_store.py` | Session 儲存機制確認與部署環境相容（預設為單機適用） |
| 錯誤訊息 | 所有含敏感操作（密碼驗證失敗、TOTP 錯誤）均以模糊錯誤回傳，防止帳號枚舉攻擊 |
| `expense_db.py` v2 | 所有函式均需傳入 `user_id`，升級自舊版時需更新所有呼叫點 |
