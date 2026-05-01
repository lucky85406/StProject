# StProject

基於 Streamlit 的柔和漸層主題 Web 應用，包含登入驗證、多頁面架構、統一 Log 系統與 AI 功能整合。

## 專案結構

```
StProject/
├── app.py                        # 主程式入口（登入 + 路由 + 全域 CSS + Footer + Log）
├── pages/
│   ├── __init__.py
│   ├── home.py                   # 首頁（歡迎訊息、KPI 指標卡片、最新消息）
│   ├── dashboard.py              # 儀表板（折線 / 長條 / 面積圖、統計卡片）
│   ├── crawler_dashboard.py      # 網頁爬蟲工作台（兩階段 Pipeline、Tag 擷取）
│   ├── image_upscaler.py         # AI 圖像超解析度（PyTorch CUDA + OpenCV 備援）
│   └── settings.py               # 設定（個人資料、密碼修改、外觀偏好）
├── core/
│   ├── session_store.py          # Session 建立 / 驗證 / 刪除
│   └── users.py                  # 帳號密碼驗證
├── models/                       # OpenCV DNN 超解析度模型快取目錄（自動建立）
├── .streamlit/
│   └── config.toml               # Streamlit 設定
├── pyproject.toml
└── uv.lock
```

## 快速開始

### 1. 安裝相依套件

```bash
uv sync
```

### 2. 安裝 Playwright 瀏覽器（爬蟲功能需要）

```bash
uv run playwright install chromium
```

### 3. 啟動應用

```bash
uv run streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

## 功能說明

| 功能 | 路徑 | 說明 |
|------|------|------|
| 🔐 登入 | `app.py` | 帳號密碼驗證，支援 URL `sid` 保留登入狀態 |
| 🏠 首頁 | `pages/home.py` | 歡迎訊息、KPI 指標卡片、最新消息列表 |
| 📊 儀表板 | `pages/dashboard.py` | 多種圖表、時間範圍篩選、資料表展示 |
| 🕸 爬蟲 | `pages/crawler_dashboard.py` | 商品 / 影片爬取、自訂 Tag 擷取、兩階段 Pipeline |
| 🖼 超解析度 | `pages/image_upscaler.py` | GPU 推理 (EDSR)、人像細節強化、PNG / JPEG 下載 |
| ⚙️ 設定 | `pages/settings.py` | 個人資料、密碼修改、外觀偏好、系統資訊 |
| 🚪 登出 | `app.py` sidebar | 清除 Session，返回登入畫面 |

## 主架構設計（app.py）

### 色系主題

全站採用柔和淺色漸層設計：

| 元素 | 色彩 |
|------|------|
| 主背景 | 米白 → 薰衣草 → 粉白 三色漸層（固定背景） |
| 側邊欄 | 純白 → 淺紫縱向漸層，右側柔和陰影 |
| 卡片 / 表面 | `#ffffff` 純白，搭配薰衣草紫邊框 |
| 主色調 | 薰衣草紫 `#7c6ff7` → 玫瑰粉 `#e879a0` 漸層 |
| 文字 | 深紫灰 `#3b3552` |
| 字型 | Nunito（內文）+ DM Mono（程式碼/標籤） |

### 側邊欄結構

```
┌─────────────────────────────┐
│  ⚡ StProject   v1.0.0      │  ← Brand 區塊
├─────────────────────────────┤
│  👤 admin                   │  ← 使用者名稱 chip
│  🚪 登出                    │  ← 登出按鈕（獨立一列，同色系）
├─────────────────────────────┤
│  ▪ 功能導覽                 │
│  ┌──────┬──────┬──────┐    │  ← 每列最多 3 個導覽按鈕
│  │ 🏠   │ 📊   │ 🕸   │    │    type="primary"（CSS 精確定位）
│  │ 首頁 │儀表板│ 爬蟲 │    │
│  └──────┴──────┴──────┘    │
│  ┌──────┬──────┐            │
│  │ 🖼   │ ⚙️   │            │
│  │超解析│ 設定 │            │
│  └──────┴──────┘            │
├─────────────────────────────┤
│  ⚙ [當前頁面] 設定參數      │  ← 動態參數面板（下半部）
│  ... 各功能專屬控制項 ...   │
└─────────────────────────────┘
```

**導覽按鈕技術細節：**
- 導覽按鈕使用 `type="primary"` → DOM `data-testid="stBaseButton-primary"`
- 登出按鈕使用預設 `type="secondary"` → DOM `data-testid="stBaseButton-secondary"`
- 兩者 CSS selector 完全獨立，不互相干擾

### 頁面標題 Hero 橫幅

每個功能頁面最上方統一渲染 Hero 橫幅，包含功能 icon、頁面標題（漸層文字）、副標題，背景帶裝飾性漸層光暈。

### 動態參數面板

側邊欄下半部根據當前頁面動態渲染對應參數，切換頁面時自動清除前頁殘留的 `session_state` 值，防止型別污染：

| 頁面 | 參數 |
|------|------|
| 🏠 首頁 | 無 |
| 📊 儀表板 | 時間範圍、圖表類型、動態效果 |
| 🕸 爬蟲 | 最大並發數、請求延遲、逾時時間、重試次數、robots.txt |
| 🖼 超解析度 | AI 模型、放大倍數、GPU 加速、人像模式、銳化強度 |
| ⚙️ 設定 | 無 |

### Footer

固定於畫面底部，半透明毛玻璃效果（`rgba(250,248,255,0.90)` + `backdrop-filter: blur`）：
- 左側：設計者姓名（Kevin Wu）、版權資訊
- 右側：當前日期、技術棧標籤

### Topbar

Streamlit 原生頂端列改為半透明毛玻璃，融入頁面漸層背景。Streamlit MPA 原生頁面導覽列（`stSidebarNav`）已透過 CSS 隱藏。

## Log 系統

統一格式：

```
時間戳  [LEVEL   ]  模組名稱                 │  訊息內容
```

功能切換時在 CMD 輸出 `═` 符號橫幅區隔：

```
════════════════════════════════════════════════════════════════════════════
  ▶  PAGE: 網頁爬蟲工作台
════════════════════════════════════════════════════════════════════════════

2026-04-19 15:42:10  [INFO    ]  pages.crawler_dashboard   │  渲染爬蟲頁面 ─ user=admin
```

各模組 Logger 命名：

| 模組 | Logger 名稱 |
|------|-------------|
| 主程式 | `app` |
| 首頁 | `pages.home` |
| 儀表板 | `pages.dashboard` |
| 爬蟲 | `pages.crawler_dashboard` |
| 超解析度 | `pages.image_upscaler` |
| 設定 | `pages.settings` |

## 測試帳號

| 帳號 | 密碼 |
|------|------|
| admin | admin123 |
| user | user123 |

## 技術棧

| 類別 | 套件 / 版本 |
|------|------------|
| 前端框架 | Streamlit ≥ 1.56 |
| 套件管理 | uv |
| AI 推理 | PyTorch ≥ 2.5（CUDA 12.1） |
| 影像處理 | OpenCV ≥ 4.13、Pillow ≥ 12 |
| 爬蟲 | httpx、selectolax、Playwright、crawlee |
| 資料驗證 | Pydantic ≥ 2.13 |
| 環境設定 | python-dotenv |
| Python | ≥ 3.12 |