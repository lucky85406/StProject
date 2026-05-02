# 🧩 core/ — 核心業務邏輯模組

本目錄包含 StProject 所有共用核心邏輯，涵蓋資料庫連線、身份驗證、Session 管理、TOTP、QR 登入與消費記錄資料存取層。所有模組均採用標準 Python logging，不直接依賴 Streamlit，可獨立測試。

---

## 目錄結構

```
core/
├── auth.py           # Auth 公開介面（re-export session_store）
├── db.py             # Supabase 連線工廠（lru_cache 單例）
├── expense_db.py     # 消費記錄資料存取層（DAL）
├── network.py        # 網路工具（取得本機 IP）
├── qr_login.py       # QR Code 圖片產生與確認 URL 建構
├── qr_store.py       # QR Token 狀態機（JSON 檔案儲存）
├── session_store.py  # 登入 Session 建立 / 驗證 / 刪除
├── totp.py           # Google Authenticator TOTP 工具
└── users.py          # 使用者帳號驗證與管理
```

---

## 🔌 db.py — Supabase 連線工廠

Supabase 客戶端的單例工廠，整個 App 生命週期只初始化一次。

```python
from core.db import get_client

client = get_client()  # 回傳快取的 supabase.Client
```

- 使用 `@lru_cache(maxsize=1)` 確保連線不重複建立
- 憑證從 `st.secrets["supabase"]` 讀取（`.streamlit/secrets.toml`）
- 使用 `service_role` key，繞過 Row Level Security（RLS），適合伺服器端操作

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

| 函式 | 說明 |
|------|------|
| `verify_login(username, password, totp_code)` | 統一登入驗證入口，回傳 `(bool, LoginReason)` |
| `verify_password(username, password)` | 僅驗證密碼（bcrypt checkpw） |
| `user_exists(username)` | 確認使用者是否存在（QR 登入用） |
| `create_user(username, password)` | 新增使用者，TOTP 預設停用 |
| `change_password(username, old_pw, new_pw)` | 修改密碼（驗證舊密碼後 bcrypt 重新 Hash） |
| `get_totp_info(username)` | 取得 `(totp_enabled, totp_secret)` |
| `save_totp_secret(username, secret)` | 儲存 TOTP 秘鑰並啟用 |
| `disable_totp(username)` | 停用 TOTP，清除 secret |

### 登入驗證流程

```
verify_login(username, password, totp_code)
    ├─ Step 1: bcrypt.checkpw(password, stored_hash)
    │       └─ 失敗 → return (False, "wrong_password")
    ├─ Step 2: totp_enabled 檢查
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
| `username` | text | 唯一帳號名稱 |
| `password` | text | bcrypt hash（rounds=12） |
| `totp_enabled` | bool | 是否已啟用 TOTP（預設 False） |
| `totp_secret` | text | Base32 TOTP 秘鑰（可為 NULL） |

---

## 🔑 session_store.py — Session 管理

管理登入後的使用者 Session，透過 URL Query Param `?sid=` 保留登入狀態（無 Cookie 依賴）。

### 主要函式

| 函式 | 說明 |
|------|------|
| `create_session(username)` | 建立 Session，回傳 UUID sid |
| `verify_session(sid)` | 驗證 sid 是否有效，回傳 username 或 None |
| `delete_session(sid)` | 刪除 Session（登出用） |

### auth.py

`core/auth.py` 為 Session 相關函式的公開介面模組，直接 re-export `session_store` 的函式，方便統一 import 路徑：

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
| `get_provisioning_uri(secret, username)` | 產生 `otpauth://` URI |
| `generate_setup_qr_png(secret, username)` | 產生設定用 QR Code（PNG bytes） |
| `verify_code(secret, code)` | 驗證 6 位數 TOTP 碼（允許 ±30 秒時鐘漂移） |

### 使用範例

```python
from core.totp import generate_secret, generate_setup_qr_png, verify_code

# 產生秘鑰與 QR
secret = generate_secret()
qr_png = generate_setup_qr_png(secret, "admin")

# 驗證使用者輸入
is_valid = verify_code(secret, "123456")
```

---

## 📱 qr_store.py — QR Token 狀態機

管理 QR Code 登入的 Token 生命週期，採本機 JSON 檔案儲存（`.qr_store.json`），適合單機部署。

### Token 狀態機

```
create_qr_token()
    └─→ status: "pending"
            │
            ├─ 手機掃描並確認 → confirm_qr_token()
            │       └─→ status: "confirmed"
            │               └─ 瀏覽器輪詢偵測 → check_qr_token()
            │                       └─ 登入成功 → consume_qr_token()（清除）
            │
            └─ 超過 120 秒 → 自動視為 "expired"
```

### 主要函式

| 函式 | 說明 |
|------|------|
| `create_qr_token()` | 建立新 Token，回傳 token_id（UUID） |
| `confirm_qr_token(token_id, username)` | 手機端確認（綁定 username） |
| `check_qr_token(token_id)` | 瀏覽器輪詢用，回傳 `(QrStatus, username)` |
| `consume_qr_token(token_id)` | 登入成功後清除 Token（防重用） |

### QrStatus 型別

```python
QrStatus = Literal["pending", "confirmed", "expired"]
```

---

## 🔗 qr_login.py — QR 登入輔助工具

負責產生可掃描的 QR Code 圖片，以及建構手機端確認頁面 URL。

### 主要函式

| 函式 | 說明 |
|------|------|
| `generate_qr_image(url)` | 將 URL 轉為 QR Code PNG bytes |
| `build_confirm_url(token_id, port)` | 建構手機端確認 URL（含 `?qr_confirm=token_id`） |

---

## 🌐 network.py — 網路工具

```python
from core.network import get_local_ip

ip = get_local_ip()  # e.g., "192.168.1.100"
```

取得本機區域網路 IP，用於在側邊欄顯示內網服務位址與產生 QR Code URL。

---

## 💳 expense_db.py — 消費記錄資料存取層

頁面層（`pages/daily_expense.py`）的所有 Supabase 操作均集中於此，實現關注點分離。

### 資料類別（dataclass）

| 類別 | 欄位 | 說明 |
|------|------|------|
| `Category` | id, name, icon, is_default, sort_order | 消費類別 |
| `Expense` | id, amount, category_id/name/icon, recorded_at, note, created_at | 消費記錄 |
| `BudgetSetting` | id, daily_limit, is_active, updated_at | 預算設定 |
| `TodaySummary` | total, expenses, is_over_budget, budget_limit | 今日彙總（計算型） |

### 主要函式

**類別管理**
- `get_all_categories()` → `list[Category]`
- `add_category(name, icon)` → `bool`
- `delete_category(category_id)` → `bool`（預設類別不可刪除）

**消費記錄**
- `add_expense(amount, category_id, recorded_at, note)` → `str | None`（回傳新建 id）
- `get_expenses_by_date(target_date)` → `list[Expense]`
- `delete_expense(expense_id)` → `bool`

**預算設定**
- `get_budget()` → `BudgetSetting | None`
- `update_budget(daily_limit, is_active)` → `bool`（upsert 語意）

### 防呆機制

- 金額 ≤ 0 時拒絕新增，記錄 Warning log
- 不允許新增「未來時間」的消費記錄
- 備註超過 200 字自動截斷
- 刪除預設類別時回傳 False 並記錄警告

---

## 🏗️ 模組依賴關係

```
app.py
  ├─ core.auth          → core.session_store
  ├─ core.users         → core.db, core.totp
  ├─ core.qr_store      （無外部依賴）
  └─ core.qr_login      → core.network

pages/daily_expense.py
  └─ core.expense_db    → core.db
```

---

## ⚠️ 注意事項

- `db.py` 的 `get_client()` 使用 `lru_cache`，在 Streamlit 多執行緒環境下需確認執行緒安全性（目前 Supabase Python Client 為執行緒安全）。
- `qr_store.py` 使用本機 JSON 檔案，**不適合多實例水平擴展部署**。如需多機部署，應將 Token 存入 Supabase 或 Redis。
- `session_store.py` 的 Session 儲存機制請確認與部署環境相容（單機適用）。
- 所有含敏感資訊的函式（密碼驗證失敗、TOTP 錯誤）均以模糊錯誤訊息對外回傳，防止帳號枚舉攻擊。
