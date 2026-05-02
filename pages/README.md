# 📄 pages/ — 功能頁面模組

本目錄包含 StProject 所有功能頁面，每個模組對外暴露 `show()` 函式，由 `app.py` 根據導覽狀態動態載入。

> **開發慣例**：每個頁面使用各自的 `logging.getLogger("pages.<module>")` 記錄器，所有 Supabase 操作透過 `core/` 模組進行，頁面層不直接呼叫 Supabase。

---

## 目錄結構

```
pages/
├── __init__.py
├── home.py               # 🏠 系統首頁
├── daily_expense.py      # 💰 每日消費記錄
├── dashboard.py          # 📊 資料儀表板
├── crawler_dashboard.py  # 🕸 網頁爬蟲工作台
├── image_upscaler.py     # 🖼 AI 圖像超解析度
└── settings.py           # ⚙️ 系統設定
```

---

## 🏠 home.py — 系統首頁

**Logger**：`pages.home`

登入後的預設落點頁面，提供系統狀態的快速總覽。

### 主要內容

- **歡迎橫幅**：顯示登入使用者名稱及當前時間
- **KPI 指標卡片**：展示系統關鍵數據（可依需求擴充）
- **最新消息列表**：公告與系統更新資訊

### 側邊欄

此頁面無額外側邊欄參數，僅顯示通用導覽與使用者資訊。

---

## 💰 daily_expense.py — 每日消費記錄

**Logger**：`pages.daily_expense`

快速記帳工具，整合 Supabase 進行資料持久化，支援類別管理與預算追蹤。所有資料以 `user_id`（UUID）進行多使用者隔離。

### 主要功能

| 功能 | 說明 |
|------|------|
| 快速記帳 | 選擇類別、輸入金額與備註，一鍵新增消費記錄 |
| 今日總覽 | 列出今日所有消費明細，計算總金額 |
| 預算追蹤 | 設定每日消費上限，超額時觸發視覺警示 |
| 類別管理 | 新增 / 刪除使用者自訂消費類別（含 Emoji 圖示） |
| 歷史記錄 | 依日期篩選、刪除個別消費紀錄 |

### 資料層（core/expense_db.py v2）

頁面透過 `core/expense_db.py` 存取 Supabase，**所有函式均傳入 `user_id` 參數**進行資料隔離：

| 資料表 | 用途 |
|--------|------|
| `expenses` | 消費記錄（金額、類別、時間、備註），含 `user_id` 欄位 |
| `categories` | 消費類別（全域預設 + 使用者自訂），使用者自訂類別含 `user_id` |
| `budget_settings` | 每日預算設定，含 `user_id` 欄位 |

### 類別顯示邏輯

```
get_all_categories(user_id)
    ├─ 全域預設類別（is_default=True, user_id IS NULL）
    └─ 使用者自訂類別（user_id = 當前使用者）
    → 合併後依 sort_order 排序回傳
```

### 側邊欄

此頁面無額外側邊欄參數。

---

## 📊 dashboard.py — 資料儀表板

**Logger**：`pages.dashboard`

圖表視覺化頁面，提供多種時間維度的資料分析。

### 主要內容

- **統計卡片**：關鍵指標快速總覽
- **折線圖**：趨勢變化分析
- **長條圖**：分類比較
- **面積圖**：累積量呈現
- **資料表格**：原始資料展示與排序

### 側邊欄參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| 時間範圍 | Selectbox | 最近 7 天 | 最近 7 天 / 30 天 / 90 天 / 本年度 |
| 圖表類型 | Selectbox | 折線圖 | 折線圖 / 長條圖 / 面積圖 |
| 啟用動態效果 | Checkbox | ✅ | 開啟圖表動畫效果 |

---

## 🕸 crawler_dashboard.py — 網頁爬蟲工作台

**Logger**：`pages.crawler_dashboard`

功能完整的爬蟲控制台，支援商品與影片兩種內容類型的解析，採兩階段 Pipeline 架構。

### 主要功能

| 功能 | 說明 |
|------|------|
| 兩階段 Pipeline | Stage 1：批量抓取頁面 → Stage 2：解析目標內容 |
| 自動偵測模式 | 自動識別商品頁 / 影片頁並選擇對應解析器 |
| 自訂 Tag 擷取 | 輸入 CSS Selector 擷取自訂欄位 |
| 爬取歷史 | 保存本次 Session 的爬取結果，可匯出為 CSV |
| 合規性控制 | 遵守 robots.txt、可設定請求間隔與逾時限制 |

### 技術架構

| 技術 | 版本 | 用途 |
|------|------|------|
| `httpx[http2]` | ≥ 0.28.1 | 非同步 HTTP 請求，支援 HTTP/2 |
| `selectolax` | ≥ 0.4.7 | 高效能 HTML 解析（比 BeautifulSoup 快 10 倍） |
| `playwright` | ≥ 1.58.0 | 處理需要 JavaScript 渲染的動態頁面 |
| `crawlee[beautifulsoup]` | ≥ 1.6.2 | 爬蟲任務佇列與並發管理 |

### 側邊欄參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| 並發數 | Slider | 3 | 同時爬取的連結數（建議 ≤ 5） |
| 請求間隔（秒） | Slider | 1.5 | 每次請求的等待時間（0.5 ~ 5.0） |
| 逾時上限（秒） | Slider | 15 | 單頁最長等待時間（5 ~ 30） |
| 單批上限 | Slider | 20 | 單次爬取的 URL 數量上限（5 ~ 50） |
| 內容類型 | Selectbox | 自動偵測 | 自動偵測 / 僅商品 / 僅影片 |
| 標籤數量上限 | Slider | 10 | 每筆結果保留的最大 Tag 數（3 ~ 20） |

### 資料模型（Pydantic v2）

```python
class CrawlItem(BaseModel):
    url: str
    name: str
    tags: list[str]
    source_platform: str
    thumbnail_url: str | None
    fetch_time_ms: int
    error: str | None
```

### Session 狀態管理

| Key | 說明 |
|-----|------|
| `crawl_history` | 本次 Session 累積的爬取結果（`list[dict]`） |
| `sb_filter` | 側邊欄篩選器目前選擇的平台（預設「全部」） |

### CSV 匯出欄位

`名稱`、`連結`、`標籤`、`平台`、`縮圖連結`、`耗時(ms)`、`狀態`

---

## 🖼 image_upscaler.py — AI 圖像超解析度

**Logger**：`pages.image_upscaler`

基於節點式工作流的影像處理頁面，GPU 可用時優先使用 **PyTorch EDSR** 進行超解析度推理，無 GPU 時自動降回 **OpenCV DNN**（CPU 備援）。

### 推理引擎選擇邏輯

```
CUDA 可用（torch.cuda.is_available()）
    └─→ PyTorch EDSR（basicsr 框架，GPU 加速）
CUDA 不可用
    └─→ OpenCV DNN（需預先下載 .pb 模型至 models/ 目錄）
```

### 工作流節點

| 節點 | 引擎 | 說明 |
|------|------|------|
| 🔵 AI 超解析度 | PyTorch EDSR / OpenCV DNN | 核心放大推理 |
| 🟢 人像細節強化 | OpenCV + PIL | 銳化、對比、亮度、飽和度、去噪 |
| 🟡 人臉銳化（Unsharp Mask） | PIL / OpenCV | 保留皮膚紋理的高頻銳化 |

### OpenCV DNN 支援模型（CPU 備援）

| 模型 | 特性 | 適合場景 |
|------|------|----------|
| EDSR | 最高品質，速度較慢 | 一般超解析度 |
| ESPCN | 即時推理速度 | 影片幀處理 |
| FSRCNN | 輕量快速 | 資源受限環境 |
| LapSRN | 漸進式放大 | 大倍數（4×）放大 |

### 下載格式

- **PNG**（無損，適合後製）
- **JPEG**（壓縮，適合分享）

### 側邊欄參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| AI 模型 | Selectbox | EDSR | EDSR / ESPCN / FSRCNN / LapSRN |
| 放大倍數 | Selectbox | 2× | 2× / 3× / 4× |
| 啟用 GPU 加速 | Checkbox | ✅ | 優先使用 CUDA 推理（偵測到 GPU 時有效） |
| 人像模式 | Checkbox | ✅ | 啟用人像細節強化節點 |
| 銳化強度 | Slider | 1.0 | 0.0 ~ 3.0 |

### models/ 目錄

OpenCV DNN 的 `.pb` 模型檔案快取於此目錄（首次使用時自動建立）。模型體積較大，建議加入 `.gitignore`。

---

## ⚙️ settings.py — 系統設定

**Logger**：`pages.settings`

使用者個人設定中心，提供帳號管理與安全性設定。

### 功能分頁

| 分頁 | 功能 |
|------|------|
| 個人資料 | 顯示帳號名稱、登入時間等基本資訊 |
| 密碼修改 | 輸入舊密碼 + 新密碼（bcrypt 重新 Hash 後存入 Supabase） |
| Google 驗證器 | 啟用 / 停用 TOTP、重新設定 QR Code、掃描新秘鑰 |
| 外觀偏好 | UI 主題偏好設定 |
| 系統資訊 | Python 版本、套件版本、GPU 狀態（CUDA 可用性）、Supabase 連線狀態 |

### TOTP 管理流程

```
啟用 TOTP
    └─→ generate_secret()
        → 顯示 QR Code（generate_setup_qr_png）
        → 使用者輸入驗證碼（verify_code）
        → 驗證通過 → save_totp_secret() 存入 Supabase

停用 TOTP
    └─→ 輸入當前 TOTP 碼確認身份（verify_code）
        → 確認通過 → disable_totp() 清除 secret
```

### 側邊欄

此頁面無額外側邊欄參數。

---

## 🔧 頁面開發規範

新增功能頁面時，請遵循以下慣例：

```python
# pages/my_feature.py
from __future__ import annotations
import logging
import streamlit as st

logger = logging.getLogger("pages.my_feature")

def show() -> None:
    """頁面主入口，由 app.py 呼叫。"""
    logger.info("渲染頁面 ─ user=%s", st.session_state.get("username"))
    # ... 頁面實作
```

接著在 `app.py` 的 `PAGE_CONFIG` 清單中新增對應設定項，系統即會自動將其納入導覽列與動態側邊欄參數面板。

### 取得當前使用者資訊

```python
# 從 session_state 取得已登入使用者的資訊
username: str = st.session_state.get("username", "")
user_id: str  = st.session_state.get("user_id", "")   # UUID，消費記錄隔離用
sid: str      = st.session_state.get("sid", "")       # Session ID
```
