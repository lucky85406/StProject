# 📄 pages/ — 功能頁面模組

本目錄包含 StProject 所有功能頁面，每個模組對外暴露 `show()` 函式，由 `app.py` 根據導覽狀態動態載入。

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

### 側邊欄參數

此頁面無額外參數，側邊欄僅顯示通用導覽與使用者資訊。

---

## 💰 daily_expense.py — 每日消費記錄

**Logger**：`pages.daily_expense`

快速記帳工具，整合 Supabase 進行資料持久化，支援類別管理與預算追蹤。

### 主要功能

| 功能 | 說明 |
|------|------|
| 快速記帳 | 選擇類別、輸入金額與備註，一鍵新增消費記錄 |
| 今日總覽 | 列出今日所有消費明細，計算總金額 |
| 預算追蹤 | 設定每日消費上限，超額時觸發視覺警示 |
| 類別管理 | 新增 / 刪除自訂消費類別（含 Emoji 圖示） |
| 歷史記錄 | 依日期篩選、刪除個別消費紀錄 |

### 資料層

頁面透過 `core/expense_db.py` 存取 Supabase，涉及以下資料表：

| 資料表 | 用途 |
|--------|------|
| `expenses` | 消費記錄（金額、類別、時間、備註） |
| `categories` | 消費類別（名稱、圖示、是否預設） |
| `budget_settings` | 每日預算設定 |

### 側邊欄參數

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
| 合規性控制 | 遵守 robots.txt、可設定請求間隔 |

### 技術架構

- **httpx + h2**：非同步 HTTP 請求，支援 HTTP/2
- **selectolax**：高效能 HTML 解析（比 BeautifulSoup 快 10 倍）
- **Playwright**：處理需要 JavaScript 渲染的動態頁面
- **crawlee**：爬蟲任務佇列與並發管理

### 側邊欄參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| 最大並發數 | Slider | 3 | 同時爬取的連結數（建議 ≤ 5） |
| 請求延遲（秒） | Slider | 1.5 | 每次請求的等待時間 |
| 逾時上限（秒） | Slider | 15 | 單頁最長等待時間 |
| 單批上限 | Slider | 20 | 單次爬取的 URL 數量上限 |
| 內容類型 | Selectbox | 自動偵測 | 自動偵測 / 僅商品 / 僅影片 |
| 標籤數量上限 | Slider | 10 | 每筆結果保留的最大 Tag 數 |

### 資料模型（Pydantic）

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

---

## 🖼 image_upscaler.py — AI 圖像超解析度

**Logger**：`pages.image_upscaler`

基於節點式工作流的影像處理頁面，GPU 可用時優先使用 PyTorch EDSR 進行超解析度推理，無 GPU 時自動降回 OpenCV DNN。

### 工作流節點

| 節點 | 說明 | 參數 |
|------|------|------|
| 🔵 AI 超解析度 | PyTorch EDSR（GPU）/ OpenCV DNN（CPU） | 模型選擇、放大倍數 |
| 🟢 人像細節強化 | 銳化、對比、亮度、飽和度、去噪 | 各項強度滑桿 |
| 🟡 人臉銳化（Unsharp Mask） | 保留皮膚紋理的高頻銳化 | 銳化強度 |

### 推理引擎選擇邏輯

```
GPU (CUDA) 可用
    └─→ PyTorch EDSR（內建架構，無需下載模型）
GPU 不可用
    └─→ OpenCV DNN（需事先下載 .pb 模型至 models/ 目錄）
```

### 支援模型（OpenCV CPU 備援）

| 模型 | 特性 |
|------|------|
| EDSR | 高品質，速度較慢 |
| ESPCN | 即時推理，適合影片 |
| FSRCNN | 輕量快速 |
| LapSRN | 漸進式放大，適合大倍數 |

### 下載輸出格式

- PNG（無損，適合後製）
- JPEG（壓縮，適合分享）

### 側邊欄參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| AI 模型 | Selectbox | EDSR | EDSR / ESPCN / FSRCNN / LapSRN |
| 放大倍數 | Selectbox | 2× | 2× / 3× / 4× |
| 啟用 GPU 加速 | Checkbox | ✅ | 優先使用 CUDA 推理 |
| 人像模式 | Checkbox | ✅ | 強化人臉細節處理 |
| 銳化強度 | Slider | 1.0 | 0.0 ~ 3.0 |

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
| 系統資訊 | Python 版本、套件版本、GPU 狀態、Supabase 連線狀態 |

### TOTP 管理流程

```
啟用 TOTP
    └─→ 產生新 secret → 顯示 QR Code → 輸入驗證碼確認 → 存入 Supabase

停用 TOTP
    └─→ 輸入當前 TOTP 碼確認身份 → 清除 totp_secret、totp_enabled=False
```

### 側邊欄參數

此頁面無額外側邊欄參數。

---

## 🔧 頁面開發規範

新增功能頁面時，請遵循以下慣例：

```python
# pages/my_feature.py
import logging
import streamlit as st

logger = logging.getLogger("pages.my_feature")

def show() -> None:
    """頁面主入口，由 app.py 呼叫"""
    logger.info("渲染頁面 ─ user=%s", st.session_state.get("username"))
    # ... 頁面實作
```

接著在 `app.py` 的 `PAGE_CONFIG` 清單中新增對應設定項，系統即會自動將其納入導覽列與動態參數面板。
