# ⚙️ .streamlit/ — Streamlit 執行設定

本目錄包含 Streamlit 的伺服器行為設定與敏感憑證設定，**不應提交至版本控制系統（.gitignore）**。

---

## 目錄結構

```
.streamlit/
├── config.toml     # Streamlit 伺服器行為設定（可公開）
└── secrets.toml    # 敏感憑證（⚠️ 不可提交至 Git）
```

---

## 📄 config.toml — 伺服器行為設定

控制 Streamlit 的執行時期行為，以下為建議設定：

```toml
[server]
# 關閉使用統計回傳（提升冷啟動速度）
gatherUsageStats = false

# 檔案變更時自動重新載入（開發模式）
runOnSave = false

[browser]
# 啟動後不自動開啟瀏覽器
serverAddress = "localhost"
gatherUsageStats = false

[theme]
# 使用 Light 基底（自訂 CSS 覆蓋細節）
base = "light"
```

> 本專案透過 `GLOBAL_CSS` 注入大量自訂樣式，`[theme]` 區塊的設定僅作為 Streamlit 元件的基礎色調底板。

---

## 🔐 secrets.toml — 敏感憑證設定

> ⚠️ **此檔案必須加入 `.gitignore`，絕不可提交至版本控制系統。**

請手動建立此檔案並填入憑證：

```toml
[supabase]
url = "https://xxxxxxxxxxxx.supabase.co"
service_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

### 取得 Supabase 憑證

1. 登入 [Supabase Dashboard](https://supabase.com/dashboard)
2. 選擇你的專案 → **Project Settings** → **API**
3. 複製：
   - **Project URL** → 填入 `url`
   - **service_role** key（**非** `anon` key）→ 填入 `service_key`

> ⚠️ `service_role` key 擁有完整資料庫存取權，務必保密。本專案使用此 key 是因為伺服器端直接操作 Supabase，繞過 Row Level Security（RLS）。

### 在程式中存取 Secrets

```python
import streamlit as st

url = st.secrets["supabase"]["url"]
key = st.secrets["supabase"]["service_key"]
```

---

## 🗄️ Supabase 資料表建立

首次部署前，需在 Supabase 建立以下資料表：

### `users` 資料表

```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      TEXT UNIQUE NOT NULL,
    password      TEXT NOT NULL,           -- bcrypt hash
    totp_enabled  BOOLEAN DEFAULT FALSE,
    totp_secret   TEXT,                    -- Base32 TOTP 秘鑰
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

### `expenses` 資料表

```sql
CREATE TABLE expenses (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    amount        NUMERIC(10, 2) NOT NULL,
    category_id   UUID REFERENCES categories(id),
    recorded_at   TIMESTAMPTZ DEFAULT NOW(),
    note          TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

### `categories` 資料表

```sql
CREATE TABLE categories (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    icon          TEXT DEFAULT '📦',
    is_default    BOOLEAN DEFAULT FALSE,
    sort_order    INT DEFAULT 100,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

### `budget_settings` 資料表

```sql
CREATE TABLE budget_settings (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    daily_limit   NUMERIC(10, 2) NOT NULL,
    is_active     BOOLEAN DEFAULT TRUE,
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 🚀 啟動指令參考

```bash
# 本機開發（預設 8501 port）
uv run streamlit run app.py

# 指定 port 並對外開放（區域網路分享）
uv run streamlit run app.py --server.address=0.0.0.0 --server.port=8501

# 關閉開發者工具列（正式部署）
uv run streamlit run app.py --server.address=0.0.0.0 \
                             --server.port=8501 \
                             --server.headless=true
```

---

## 📝 .gitignore 建議設定

確保以下項目不被提交至版本控制：

```gitignore
# Streamlit 敏感設定
.streamlit/secrets.toml

# QR Token 暫存檔
.qr_store.json

# Python
__pycache__/
*.pyc
.venv/

# uv
.python-version
```
