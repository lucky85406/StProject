# ⚡ StProject

基於 **Streamlit** 的全端 Web 管理平台，整合 AI 推理、網路爬蟲、每日消費記錄與多因素身份驗證（TOTP + QR Code），採用柔和漸層 UI 主題設計。

> Python ≥ 3.12 · uv · Streamlit ≥ 1.56.0 · Supabase · PyTorch 2.5.1 (CUDA 12.1)

---

## 📁 專案結構

```
StProject/
├── app.py                  # 主程式入口（登入路由、全域 CSS、Footer、Log）
├── pages/                  # 各功能頁面模組
│   ├── __init__.py
│   ├── home.py             # 🏠 系統首頁（歡迎橫幅、KPI 總覽）
│   ├── daily_expense.py    # 💰 每日消費記錄（多使用者隔離）
│   ├── dashboard.py        # 📊 資料儀表板（圖表視覺化）
│   ├── crawler_dashboard.py# 🕸 網頁爬蟲工作台（兩階段 Pipeline）
│   ├── image_upscaler.py   # 🖼 AI 圖像超解析度（GPU/CPU 自動切換）
│   └── settings.py         # ⚙️ 系統設定（密碼、TOTP、系統資訊）
├── core/                   # 共用核心邏輯（無 Streamlit 依賴，可獨立測試）
│   ├── auth.py             # Auth 公開介面（re-export session_store）
│   ├── db.py               # Supabase 連線工廠（lru_cache 單例）
│   ├── expense_db.py       # 消費記錄 DAL（v2 多使用者 user_id 隔離）
│   ├── network.py          # 網路工具（取得本機 IP）
│   ├── qr_login.py         # QR Code 圖片產生與確認 URL 建構
│   ├── qr_store.py         # QR Token 狀態機（JSON 檔案儲存）
│   ├── session_store.py    # 登入 Session 建立 / 驗證 / 刪除
│   ├── totp.py             # Google Authenticator TOTP（RFC 6238）
│   └── users.py            # 使用者帳號驗證與管理
├── models/                 # OpenCV DNN 模型快取（首次使用時自動建立）
├── .streamlit/
│   ├── config.toml         # Streamlit 伺服器行為設定
│   └── secrets.toml        # 敏感憑證（⚠️ 不可提交 Git）
├── .cursor/
│   └── rules               # Cursor AI 協作規則（Git Commit 格式規範）
├── pyproject.toml          # 專案依賴宣告（uv 管理）
└── uv.lock                 # 鎖定版本快照
```

### 📄 子目錄說明文件

| 目錄 | README | 說明 |
|------|--------|------|
| `pages/` | [pages/README.md](pages/README.md) | 所有功能頁面（首頁、儀表板、爬蟲、超解析度、消費記錄、設定） |
| `core/` | [core/README.md](core/README.md) | 共用核心模組（Supabase、Auth、TOTP、QR 登入、Session） |
| `.streamlit/` | [.streamlit/README.md](.streamlit/README.md) | Streamlit 執行環境設定與 Supabase 資料表 DDL |

---

## 🚀 環境需求

| 項目 | 需求 |
|------|------|
| Python | ≥ 3.12 |
| 套件管理 | [uv](https://docs.astral.sh/uv/) |
| GPU（選用） | CUDA 12.1 相容顯示卡（AI 超解析度 GPU 加速） |
| 資料庫 | Supabase 專案（需配置 `secrets.toml`） |

---

## ⚡ 快速開始

### 1. 安裝套件

```bash
uv sync
```

### 2. 設定 Supabase 憑證

建立 `.streamlit/secrets.toml`，填入你的 Supabase 連線資訊：

```toml
[supabase]
url = "https://xxxxxxxxxxxx.supabase.co"
service_key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

> ⚠️ 請使用 **service_role** key（非 `anon` key），以繞過 Row Level Security 進行伺服器端操作。

### 3. 安裝爬蟲瀏覽器（爬蟲功能需要）

```bash
uv run playwright install chromium
```

### 4. 建立 Supabase 資料表

請參閱 [.streamlit/README.md](.streamlit/README.md) 中的完整 DDL 建立所有必要資料表。

### 5. 啟動應用程式

```bash
# 本機開發（預設 8501 port）
uv run streamlit run app.py

# 指定 port 並對外開放（區域網路分享）
uv run streamlit run app.py --server.address=0.0.0.0 --server.port=8501

# 正式部署（關閉開發者工具列）
uv run streamlit run app.py \
    --server.address=0.0.0.0 \
    --server.port=8501 \
    --server.headless=true
```

---

## 📦 依賴套件一覽

以下所有依賴版本均鎖定於 `uv.lock`，由 `pyproject.toml` 宣告：

| 套件 | 版本 | 用途 |
|------|------|------|
| `streamlit` | ≥ 1.56.0 | Web UI 框架 |
| `supabase` | ≥ 2.29.0 | 資料庫（PostgreSQL 雲端服務） |
| `torch` | ≥ 2.5.1 (CUDA 12.1) | AI 超解析度 GPU 推理 |
| `torchvision` | ≥ 0.20.1 | 影像模型支援 |
| `basicsr` | ≥ 1.4.2 | EDSR 超解析度架構 |
| `opencv-python` | ≥ 4.13.0.92 | 影像處理、DNN CPU 推理 |
| `opencv-contrib-python` | ≥ 4.13.0.92 | OpenCV 擴充模組（DNN SR） |
| `pillow` | ≥ 12.2.0 | 影像 I/O |
| `numpy` | ≥ 2.4.4 | 數值運算 |
| `bcrypt` | ≥ 5.0.0 | 密碼雜湊（rounds=12） |
| `pyotp` | ≥ 2.9.0 | TOTP 實作（RFC 6238） |
| `qrcode[pil]` | ≥ 8.2 | QR Code 產生 |
| `crawlee[beautifulsoup]` | ≥ 1.6.2 | 爬蟲任務佇列管理 |
| `httpx[http2]` | ≥ 0.28.1 | 非同步 HTTP 請求（HTTP/2） |
| `playwright` | ≥ 1.58.0 | 動態頁面渲染（JS 支援） |
| `selectolax` | ≥ 0.4.7 | 高效能 HTML 解析 |
| `pydantic` | ≥ 2.13.2 | 爬蟲資料模型驗證 |
| `requests` | ≥ 2.33.1 | 同步 HTTP 工具 |
| `python-dotenv` | ≥ 1.2.2 | 環境變數載入 |

> **PyTorch 安裝來源**：透過 `pyproject.toml` 的 `[[tool.uv.index]]` 設定，`torch` 與 `torchvision` 強制從 `https://download.pytorch.org/whl/cu121` 安裝 CUDA 12.1 版本，採 `unsafe-best-match` 策略解析依賴衝突。

---

## 🔐 登入系統架構

```
使用者訪問 app.py
    │
    ├─ 已有 ?sid= Query Param → verify_session() → 恢復登入狀態
    │
    ├─ 帳號密碼登入（Tab 1）
    │       ├─ verify_login(username, password, totp_code)
    │       ├─ TOTP 未設定 → 強制 TOTP Enrollment 閘門
    │       └─ 成功 → create_session() → 寫入 ?sid= Query Param
    │
    └─ QR Code 登入（Tab 2）
            ├─ create_qr_token() → 產生 QR Code 圖片
            ├─ @st.fragment(run_every=3) 輪詢 check_qr_token()
            ├─ 手機掃碼確認 → confirm_qr_token()
            ├─ TOTP 未設定 → 同樣引導至 Enrollment 閘門
            └─ 成功 → create_session() → 寫入 ?sid= Query Param
```

---

## 🗄️ 資料庫 Schema 摘要

| 資料表 | 說明 |
|--------|------|
| `users` | 使用者帳號（bcrypt 密碼、TOTP 設定） |
| `expenses` | 消費記錄（含 `user_id` 欄位，多使用者隔離） |
| `categories` | 消費類別（全域預設 + 使用者自訂，含 `user_id`） |
| `budget_settings` | 每日預算設定（含 `user_id`） |

詳細 DDL 請參閱 [.streamlit/README.md](.streamlit/README.md)。

---

## 🛠️ 開發工具設定

### Cursor AI 協作規則（`.cursor/rules`）

Git Commit 訊息格式：

```
<type>(<file>): <what was done>
```

類型：`feat` / `fix` / `refactor` / `perf` / `style` / `docs` / `test` / `chore`

規則：英文、72 字以內、現在式、單行、無 body。

範例：
```
Feat(app): Add session restore logic via URL query param
Fix(image_upscaler): Remove redundant pil_to_cv2 conversion in run_pipeline
Perf(image_upscaler): Release VRAM cache after GPU inference
```

---

## 📝 .gitignore 建議設定

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

# OpenCV DNN 模型（體積較大，建議另行管理）
models/
```

---

## 📄 授權

本專案為私人專案，未附授權聲明。
