# ⚡ StProject

基於 **Streamlit** 的全端 Web 管理平台，整合 AI 推理、OCR 文字辨識、網路爬蟲、每日消費記錄與多因素身份驗證（TOTP + QR Code），採用柔和漸層 UI 主題設計。

> Python ≥ 3.12 · uv · Streamlit ≥ 1.56.0 · Supabase · PyTorch 2.5.1 (CUDA 12.1)

---

## 📁 專案結構

```
StProject/
├── app.py                  # 主程式入口（登入路由、全域 CSS、Footer、Log）
├── pages/                  # 各功能頁面模組
│   ├── __init__.py
│   ├── home.py             # 🏠 系統首頁（歡迎橫幅、功能導覽卡片）
│   ├── daily_expense.py    # 💰 每日消費記錄（多使用者隔離）
│   ├── dashboard.py        # 📊 資料儀表板（圖表視覺化）
│   ├── crawler_dashboard.py# 🕸 網頁爬蟲工作台（兩階段 Pipeline）
│   ├── image_upscaler.py   # 🖼 AI 圖像超解析度（GPU/CPU 自動切換）
│   ├── ocr_scanner.py      # 🔍 OCR 文字辨識（EasyOCR + PDF 批次解析）
│   └── settings.py         # ⚙️ 系統設定（密碼、TOTP、系統資訊）
├── core/                   # 共用核心邏輯（無 Streamlit 依賴，可獨立測試）
│   ├── auth.py             # Auth 公開介面（re-export session_store）
│   ├── db.py               # Supabase 連線工廠（lru_cache 單例）
│   ├── expense_db.py       # 消費記錄 DAL（v2 多使用者 user_id 隔離）
│   ├── network.py          # 網路工具（取得本機 IP）
│   ├── ocr_engine.py       # OCR 推理引擎（EasyOCR 封裝 + 圖像預處理）
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

| 目錄          | README                                       | 說明                                                              |
| ------------- | -------------------------------------------- | ----------------------------------------------------------------- |
| `pages/`      | [pages/README.md](pages/README.md)           | 所有功能頁面（首頁、儀表板、爬蟲、超解析度、OCR、消費記錄、設定） |
| `core/`       | [core/README.md](core/README.md)             | 共用核心模組（Supabase、Auth、TOTP、QR 登入、Session、OCR 引擎）  |
| `.streamlit/` | [.streamlit/README.md](.streamlit/README.md) | Streamlit 執行環境設定與 Supabase 資料表 DDL                      |

---

## 🗺️ 功能頁面一覽

| 頁面            | 圖示 | 說明                                             |
| --------------- | ---- | ------------------------------------------------ |
| 系統首頁        | 🏠   | 登入後落點、KPI 總覽、功能導覽卡片               |
| 每日消費記錄    | 💰   | 快速記帳、預算追蹤、多類別、歷史查詢             |
| 資料儀表板      | 📊   | 趨勢分析、折線 / 長條 / 面積圖、時間維度篩選     |
| 網頁爬蟲工作台  | 🕸   | 兩階段 Pipeline、商品/影片自動偵測、CSV 匯出     |
| AI 圖像超解析度 | 🖼   | EDSR / ESPCN / FSRCNN / LapSRN，GPU/CPU 自動切換 |
| OCR 文字辨識    | 🔍   | EasyOCR 多語言、PDF 批次解析、CSV 匯出辨識結果   |
| 系統設定        | ⚙️   | 修改密碼、TOTP 設定 / 停用、系統資訊             |

---

## 🚀 環境需求

| 項目        | 需求                                         |
| ----------- | -------------------------------------------- |
| Python      | ≥ 3.12                                       |
| 套件管理    | [uv](https://docs.astral.sh/uv/)             |
| GPU（選用） | CUDA 12.1 相容顯示卡（AI 超解析度 GPU 加速） |
| 資料庫      | Supabase 專案（需配置 `secrets.toml`）       |

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
uv run streamlit run app.py
uv run streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

---

## 📦 主要依賴套件

| 套件                     | 版本             | 用途                                        |
| ------------------------ | ---------------- | ------------------------------------------- |
| `streamlit`              | ≥ 1.56.0         | Web UI 框架                                 |
| `supabase`               | ≥ 2.29.0         | 資料庫 ORM（PostgreSQL）                    |
| `torch` / `torchvision`  | ≥ 2.5.1 / 0.20.1 | PyTorch 深度學習（CUDA 12.1）               |
| `basicsr`                | ≥ 1.4.2          | EDSR 超解析度模型框架                       |
| `easyocr`                | ≥ 1.7.2          | OCR 推理引擎（支援 80+ 語言）               |
| `pymupdf`                | ≥ 1.27.2.3       | PDF 解析與頁面渲染                          |
| `opencv-contrib-python`  | ≥ 4.13.0.92      | 圖像處理與 DNN 超解析度                     |
| `playwright`             | ≥ 1.58.0         | 動態頁面爬蟲（Chromium）                    |
| `crawlee[beautifulsoup]` | ≥ 1.6.2          | 爬蟲任務佇列管理                            |
| `httpx[http2]`           | ≥ 0.28.1         | 非同步 HTTP 請求（HTTP/2）                  |
| `selectolax`             | ≥ 0.4.7          | 高效能 HTML 解析                            |
| `pydantic`               | ≥ 2.13.2         | 資料模型與驗證                              |
| `bcrypt`                 | ≥ 5.0.0          | 密碼 Hash（rounds=12）                      |
| `pyotp`                  | ≥ 2.9.0          | TOTP（RFC 6238，Google Authenticator 相容） |
| `qrcode[pil]`            | ≥ 8.2            | QR Code 圖片產生                            |

---

## 🔐 驗證流程

```
登入頁（app.py）
    ├─ 密碼登入
    │    ├─ verify_password()          # bcrypt 驗證
    │    ├─ [TOTP 啟用時] verify_code() # RFC 6238 驗證
    │    └─ create_session()           # UUID Session Token
    │
    └─ QR Code 掃描登入
         ├─ create_qr_token()          # 產生一次性 Token
         ├─ generate_qr_image()        # 生成 QR PNG
         ├─ check_qr_token()           # 輪詢掃描狀態（3 秒）
         └─ consume_qr_token()         # 確認後建立 Session
```

---

## 🎨 UI 設計系統

本專案採用統一的「薰衣草紫 → 玫瑰粉」漸層設計 Token，透過 `app.py` 的 `GLOBAL_CSS` 全域注入：

| Token       | 值                          | 說明                 |
| ----------- | --------------------------- | -------------------- |
| `--bg`      | `#f5f3ff`                   | 全域背景（米白帶粉） |
| `--accent`  | `#7c6ff7`                   | 主色調（薰衣草紫）   |
| `--accent2` | `#e879a0`                   | 輔助色（玫瑰粉）     |
| `--grad`    | `135deg, #7c6ff7 → #e879a0` | 標準漸層             |
| `--success` | `#10b981`                   | 成功狀態（綠）       |
| `--warn`    | `#f59e0b`                   | 警告狀態（琥珀）     |
| `--danger`  | `#ef4444`                   | 危險狀態（紅）       |

---

## 📝 Git Commit 規範

本專案使用 `.cursor/rules` 定義的 Commit 格式：

```
<type>(<file>): <what was done>
```

**類型**：`feat` / `fix` / `refactor` / `perf` / `style` / `docs` / `test` / `chore`

```bash
# 範例
feat(ocr_scanner): Add PDF multi-page navigation with page selector
fix(expense_db): Handle None user_id in get_all_categories query
docs(README): Update pages structure with ocr_scanner module
```

---

## 🗄️ 資料庫 Schema 概覽

| 資料表            | 主要欄位                                                    | 說明                              |
| ----------------- | ----------------------------------------------------------- | --------------------------------- |
| `users`           | `id`, `username`, `password`, `totp_enabled`, `totp_secret` | 使用者帳號（bcrypt + TOTP）       |
| `expenses`        | `id`, `user_id`, `amount`, `category_id`, `note`, `date`    | 消費記錄（多使用者隔離）          |
| `categories`      | `id`, `user_id`, `name`, `icon`, `is_default`, `sort_order` | 消費類別（全域預設 + 使用者自訂） |
| `budget_settings` | `id`, `user_id`, `daily_budget`                             | 每日預算設定                      |

完整 DDL 請見 [.streamlit/README.md](.streamlit/README.md)。

## 安裝外部依賴模組

執行以下指令下載必要模組（來源：fffiloni/diffusers-image-outpaint）：

```powershell
curl.exe -O https://huggingface.co/spaces/fffiloni/diffusers-image-outpaint/raw/main/controlnet_union.py
curl.exe -O https://huggingface.co/spaces/fffiloni/diffusers-image-outpaint/raw/main/pipeline_fill_sd_xl.py
```
