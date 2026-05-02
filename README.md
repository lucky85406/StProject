# ⚡ StProject

基於 **Streamlit** 的全端 Web 管理平台，整合 AI 推理、網路爬蟲、消費記錄與多因素身份驗證，採用柔和漸層 UI 主題設計。

> Python ≥ 3.12 · uv · Streamlit ≥ 1.56 · Supabase · PyTorch CUDA 12.1

---

## 📁 專案結構

```
StProject/
├── app.py                  # 主程式入口（登入路由、全域 CSS、Footer、Log）
├── pages/                  # 各功能頁面模組
├── core/                   # 共用核心邏輯（DB、Auth、Session、TOTP、QR）
├── models/                 # OpenCV DNN 模型快取（自動建立）
├── .streamlit/             # Streamlit 執行設定
├── pyproject.toml          # 專案依賴宣告（uv 管理）
└── uv.lock                 # 鎖定版本快照
```

### 📄 子目錄說明文件

| 目錄 | README | 說明 |
|------|--------|------|
| `pages/` | [pages/README.md](pages/README.md) | 所有功能頁面（首頁、儀表板、爬蟲、超解析度、消費記錄、設定） |
| `core/` | [core/README.md](core/README.md) | 共用核心模組（Supabase、Auth、TOTP、QR 登入、Session） |
| `.streamlit/` | [.streamlit/README.md](.streamlit/README.md) | Streamlit 執行環境設定 |

---

## 🚀 環境需求

| 項目 | 需求 |
|------|------|
| Python | ≥ 3.12 |
| 套件管理 | [uv](https://docs.astral.sh/uv/) |
| GPU（選用） | CUDA 12.1 相容顯示卡（AI 超解析度加速用） |
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

### 3. 安裝爬蟲瀏覽器（爬蟲功能需要）

```bash
uv run playwright install chromium
```

### 4. 啟動應用

```bash
# 本機開發
uv run streamlit run app.py

# 區域網路分享（可讓同網段裝置存取）
uv run streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

瀏覽器開啟 `http://localhost:8501` 即可進入登入畫面。

---

## 🔐 登入方式

本系統支援三種登入流程，所有帳號均強制啟用 **Google Authenticator（TOTP）雙因素驗證**：

| 方式 | 說明 |
|------|------|
| 帳號密碼 + TOTP | 輸入帳號、密碼及 6 位數驗證碼 |
| QR Code 掃描 | 電腦顯示 QR，手機掃描後在手機端輸入憑證確認 |
| 首次登入閘門 | 未啟用 TOTP 的帳號，登入後強制引導完成 Google Authenticator 設定 |

> 測試帳號：`admin / admin123`　或　`user / user123`

---

## 🧩 功能一覽

| 功能 | 入口 | 說明 |
|------|------|------|
| 🏠 系統首頁 | `pages/home.py` | 歡迎訊息、KPI 卡片、最新消息 |
| 💰 每日消費 | `pages/daily_expense.py` | 快速記帳、今日總覽、預算追蹤 |
| 📊 儀表板 | `pages/dashboard.py` | 折線 / 長條 / 面積圖、時間篩選 |
| 🕸 網頁爬蟲 | `pages/crawler_dashboard.py` | 兩階段 Pipeline、Tag 擷取、並發控制 |
| 🖼 AI 超解析度 | `pages/image_upscaler.py` | PyTorch EDSR + OpenCV 備援、工作流節點 |
| ⚙️ 設定 | `pages/settings.py` | 個人資料、密碼修改、TOTP 管理、系統資訊 |

---

## 🎨 UI 主題

全站採用柔和淺色漸層設計語言：

- **主色調**：薰衣草紫 `#7c6ff7` → 玫瑰粉 `#e879a0`
- **背景**：米白 → 薰衣草 → 粉白三色漸層（固定）
- **字型**：[Nunito](https://fonts.google.com/specimen/Nunito)（內文）+ [DM Mono](https://fonts.google.com/specimen/DM+Mono)（標籤 / 程式碼）
- **Footer**：毛玻璃效果固定於底部，顯示作者資訊與技術棧標籤
- **Topbar**：半透明毛玻璃，融入頁面漸層背景

---

## 📦 技術棧

| 類別 | 套件 |
|------|------|
| 前端框架 | Streamlit ≥ 1.56 |
| 套件管理 | uv |
| 資料庫 | Supabase（PostgreSQL） |
| AI 推理 | PyTorch ≥ 2.5（CUDA 12.1） |
| 影像處理 | OpenCV ≥ 4.13、Pillow ≥ 12、BasicSR |
| 爬蟲 | httpx、selectolax、Playwright、crawlee |
| 身份驗證 | bcrypt、pyotp、qrcode |
| 資料驗證 | Pydantic ≥ 2.13 |
| 環境設定 | python-dotenv |

---

## 📝 Log 系統

統一格式輸出至 stdout，功能切換時自動插入區隔橫幅：

```
════════════════════════════════════════════════════════════════════════════
  ▶  PAGE: 網頁爬蟲工作台
════════════════════════════════════════════════════════════════════════════

2026-05-02 10:00:00  [INFO    ]  pages.crawler_dashboard   │  渲染爬蟲頁面 ─ user=admin
```

---

*© 2026 Kevin Wu · Built with Streamlit & uv*
