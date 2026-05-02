# ⚙️ .streamlit/ — Streamlit 執行設定

本目錄包含 Streamlit 的伺服器行為設定與敏感憑證設定。

> ⚠️ `secrets.toml` **不應提交至版本控制系統（加入 `.gitignore`）**

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

# 檔案變更時是否自動重新載入（開發模式建議開啟）
runOnSave = false

[browser]
serverAddress = "localhost"
gatherUsageStats = false

[theme]
# 使用 Light 基底（自訂 CSS 覆蓋細節）
base = "light"
```

> 本專案透過 `app.py` 的 `GLOBAL_CSS` 注入大量自訂樣式（薰衣草紫 → 玫瑰粉漸層主題），`[theme]` 區塊僅作為 Streamlit 元件的基礎色調底板。

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

## 🗄️ Supabase 資料表建立 DDL

首次部署前，需在 Supabase SQL Editor 執行以下建表語句：

### `users` 資料表

```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username      TEXT UNIQUE NOT NULL,
    password      TEXT NOT NULL,           -- bcrypt hash (rounds=12)
    totp_enabled  BOOLEAN DEFAULT FALSE,
    totp_secret   TEXT,                    -- Base32 TOTP 秘鑰（NULL 表示未啟用）
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

### `categories` 資料表

> ⚠️ `user_id` 為可為 NULL 的欄位：`NULL` 表示全域預設類別，有值表示使用者自訂類別。

```sql
CREATE TABLE categories (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    icon          TEXT DEFAULT '📦',
    is_default    BOOLEAN DEFAULT FALSE,
    sort_order    INT DEFAULT 100,
    user_id       UUID REFERENCES users(id) ON DELETE CASCADE,  -- NULL = 全域預設
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 建議索引（加速依使用者查詢）
CREATE INDEX idx_categories_user_id ON categories(user_id);
```

### `expenses` 資料表

```sql
CREATE TABLE expenses (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    amount        NUMERIC(10, 2) NOT NULL CHECK (amount > 0),
    category_id   UUID REFERENCES categories(id) ON DELETE SET NULL,
    recorded_at   TIMESTAMPTZ DEFAULT NOW(),
    note          TEXT,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 建議索引（加速依使用者 + 日期查詢）
CREATE INDEX idx_expenses_user_date ON expenses(user_id, recorded_at DESC);
```

### `budget_settings` 資料表

```sql
CREATE TABLE budget_settings (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    daily_limit   NUMERIC(10, 2) NOT NULL CHECK (daily_limit > 0),
    is_active     BOOLEAN DEFAULT TRUE,
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 建議索引（每位使用者通常只有一筆有效預算）
CREATE UNIQUE INDEX idx_budget_user_active ON budget_settings(user_id) WHERE is_active = TRUE;
```

### 預設類別種子資料（選用）

```sql
-- 插入全域預設類別（user_id 為 NULL）
INSERT INTO categories (name, icon, is_default, sort_order, user_id) VALUES
    ('餐飲',   '🍜', TRUE, 10, NULL),
    ('交通',   '🚇', TRUE, 20, NULL),
    ('購物',   '🛍', TRUE, 30, NULL),
    ('娛樂',   '🎮', TRUE, 40, NULL),
    ('醫療',   '💊', TRUE, 50, NULL),
    ('住宿',   '🏠', TRUE, 60, NULL),
    ('其他',   '📦', TRUE, 99, NULL);
```

---

## 🚀 啟動指令參考

```bash
# 本機開發（預設 8501 port）
uv run streamlit run app.py

# 指定 port 並對外開放（區域網路分享 / QR Code 登入需要區域網路 IP）
uv run streamlit run app.py --server.address=0.0.0.0 --server.port=8501

# 正式部署（關閉開發者工具列、Headless 模式）
uv run streamlit run app.py \
    --server.address=0.0.0.0 \
    --server.port=8501 \
    --server.headless=true
```

> **QR Code 登入注意**：此功能仰賴 `core/network.get_local_ip()` 取得區域網路 IP 來建構確認 URL。若要讓手機掃碼可正常確認，應用程式必須以 `--server.address=0.0.0.0` 對外開放，且手機與伺服器在同一區域網路內。

---

## 📝 .gitignore 建議設定

確保以下項目不被提交至版本控制：

```gitignore
# Streamlit 敏感設定
.streamlit/secrets.toml

# QR Token 暫存檔（qr_store.py 使用）
.qr_store.json

# Python
__pycache__/
*.pyc
.venv/

# uv
.python-version

# OpenCV DNN 模型快取（體積較大）
models/
```
