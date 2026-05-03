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
├── ocr_scanner.py        # 🔍 OCR 文字辨識（EasyOCR + PDF 批次）
└── settings.py           # ⚙️ 系統設定
```

---

## 🏠 home.py — 系統首頁

**Logger**：`pages.home`

登入後的預設落點頁面，提供系統功能的快速導覽入口。

### 主要內容

- **歡迎橫幅**：顯示登入使用者名稱及當前日期時間
- **功能導覽卡片**（6 張，與 `app.py` 的 `PAGE_CONFIG` 同步）：
  - 💰 每日消費記錄、📊 資料儀表板、🕸 網頁爬蟲工作台
  - 🖼 AI 圖像超解析度、🔍 OCR 文字辨識、⚙️ 系統設定
- 點擊卡片直接切換至對應功能頁（`_navigate_to(page_id)`）

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
| 預算追蹤 | 設定每日消費上限，超額時觸發視覺警示（紅色橫幅） |
| 類別管理 | 新增 / 刪除使用者自訂消費類別（含 Emoji 圖示） |
| 歷史記錄 | 依日期區間 + 類別篩選、編輯 / 軟刪除個別消費紀錄 |

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

圖表視覺化頁面，提供多種時間維度的消費資料分析。

### 主要內容

- **統計卡片**：關鍵指標快速總覽（總消費、日均消費、最高單筆等）
- **折線圖**：時間趨勢變化分析
- **長條圖**：各類別消費分類比較
- **面積圖**：累積消費量呈現
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
| 並發數 | Slider | 3 | 同時爬取的連結數（1 ~ 8，建議 ≤ 5） |
| 請求間隔（秒） | Slider | 1.5 | 每次請求的等待時間（0.5 ~ 5.0） |
| 逾時上限（秒） | Slider | 15 | 單頁最長等待時間（5 ~ 30） |
| 單批上限 | Slider | 20 | 單次爬取的 URL 數量上限（5 ~ 50） |
| 內容類型 | Selectbox | 自動偵測 | 自動偵測 / 僅商品 / 僅影片 |

### 資料模型（Pydantic v2）

```python
class CollectedItem(BaseModel):
    content_type: ContentType       # 商品 / 影片
    name: str
    url: str
    tags: list[str]
    source_platform: str
    thumbnail_url: str | None
    fetch_time_ms: int
    error: str | None
```

### Session 狀態管理

| Key | 型別 | 說明 |
|-----|------|------|
| `crawl_history` | `list[dict]` | 本次 Session 累積的爬取結果 |
| `sb_filter` | `str` | 側邊欄篩選器目前選擇的平台（預設「全部」） |

### CSV 匯出欄位

`類型`、`名稱`、`連結`、`標籤`、`平台`、`縮圖連結`、`耗時(ms)`、`狀態`

---

## 🖼 image_upscaler.py — AI 圖像超解析度

**Logger**：`pages.image_upscaler`

基於節點式工作流的影像處理頁面，GPU 可用時優先使用 **PyTorch EDSR** 進行超解析度推理，無 GPU 時自動降回 **OpenCV DNN**（CPU 備援）。

### 推理引擎選擇邏輯

```
CUDA 可用（torch.cuda.is_available()）
    └─→ PyTorch EDSR（basicsr 框架，GPU 加速）
CUDA 不可用
    └─→ OpenCV DNN（.pb 模型快取於 models/ 目錄，CPU 執行）
```

### 工作流節點

| 節點 | 引擎 | 說明 |
|------|------|------|
| 🔵 AI 超解析度 | PyTorch EDSR / OpenCV DNN | 核心放大推理節點 |
| 🟢 人像細節強化 | OpenCV + PIL | 銳化、對比、亮度、飽和度、去噪 |
| 🟡 人臉銳化（Unsharp Mask） | PIL / OpenCV | 保留皮膚紋理的高頻細節強化 |

### 支援模型

| 模型 | 說明 | 最高倍率 |
|------|------|---------|
| **EDSR** | 最高品質，GPU 推薦（預設） | 4× |
| **ESPCN** | 速度優先，適合即時場景 | 4× |
| **FSRCNN** | 平衡速度與品質 | 4× |
| **LapSRN** | 漸進式放大，適合低解析度輸入 | 4× |

### 側邊欄參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| AI 模型 | Selectbox | EDSR | EDSR / ESPCN / FSRCNN / LapSRN |
| 放大倍數 | Selectbox | 2× | 2× / 3× / 4× |
| 啟用 GPU 加速 | Checkbox | ✅ | 優先使用 CUDA 推理 |
| 人像細節強化模式 | Checkbox | ☐ | 追加人像後處理節點 |
| 銳化強度 | Slider | 1.2 | 0.0 ~ 3.0，控制全域銳化力道 |

### 側邊欄 GPU 資訊面板

- 顯示顯示卡名稱、總 VRAM、已用 VRAM
- 提供「🧹 釋放 GPU 快取」按鈕（`torch.cuda.empty_cache()`）

---

## 🔍 ocr_scanner.py — OCR 文字辨識

**Logger**：`pages.ocr_scanner`

以 EasyOCR 為核心的光學文字辨識頁面，支援圖片與 PDF 批次解析，提供多語言辨識、信心度篩選與 CSV 匯出功能。所有 OCR 推理邏輯封裝於 `core/ocr_engine.py`。

### 主要功能

| 功能 | 說明 |
|------|------|
| 多格式上傳 | 支援 PNG / JPG / JPEG / WEBP / BMP / PDF，單檔最大 20 MB |
| PDF 多頁導覽 | PDF 最多處理前 10 頁，提供逐頁選擇器 |
| 圖像預處理 | 高斯去噪 + 霍夫直線傾斜校正（Deskew）+ 二值化（可選） |
| 多語言辨識 | 繁體中文+英文 / 英文 / 日文+英文 / 韓文+英文 |
| 信心度篩選 | 最低信心度門檻（0.1 ~ 1.0），過濾低品質辨識結果 |
| 結果展示 | 雙欄佈局：原圖標注 BBox + 文字結果表格 |
| 全文複製 | 一鍵複製所有辨識文字（依 Y 軸排序，模擬閱讀順序） |
| CSV 匯出 | 匯出包含 BBox 座標與信心度的完整辨識資料 |

### 核心流程

```
上傳檔案
    ↓
load_file_as_images()          # PDF → 逐頁渲染 / 圖片 → PIL Image
    ↓
preprocess_image()             # 去噪 → Deskew → 二值化（可選）
    ↓
[使用者點擊「▶ 開始辨識」]
    ↓
run_ocr()                      # EasyOCR Reader + 信心度篩選
    ↓
post_process()                 # 依 Y 軸座標排序、合併全文字串
    ↓
展示結果 + 匯出 CSV
```

### 側邊欄參數

| 參數 | 類型 | 預設值 | Session Key | 說明 |
|------|------|--------|-------------|------|
| 辨識語言 | Selectbox | 繁體中文+英文 | `ocr_lang` | 傳入 EasyOCR 語言代碼 |
| 最低信心度 | Slider | 0.5 | `ocr_confidence` | 低於此值的結果將被過濾 |
| 啟用圖像預處理 | Checkbox | ✅ | `ocr_preprocess` | 高斯去噪是否啟用 |
| 啟用傾斜校正 | Checkbox | ✅ | `ocr_deskew` | 霍夫直線 Deskew |
| 啟用 GPU | Checkbox | ✅ | `ocr_gpu` | EasyOCR GPU 推理 |
| PDF DPI | Selectbox | 200 DPI | `ocr_pdf_dpi` | PDF 頁面渲染解析度（100/200/300 DPI） |

### Session 狀態管理

| Key | 型別 | 說明 |
|-----|------|------|
| `ocr_results` | `list[dict]` | 辨識結果（含 bbox、text、confidence） |
| `ocr_fulltext` | `str` | 合併後的完整辨識文字（Y 軸排序） |
| `ocr_cv_img` | `np.ndarray` | 預處理後的 OpenCV 圖像（用於 BBox 繪製） |
| `ocr_text_display` | `str` | 顯示用文字（可在 UI 中直接編輯） |

### CSV 匯出欄位

`序號`、`辨識文字`、`信心度`、`左上X`、`左上Y`、`右下X`、`右下Y`

> 匯出時使用 `utf-8-sig`（BOM）編碼，確保在 Excel 中正確顯示中文。

### 語言對照表

| UI 顯示 | EasyOCR 語言代碼 |
|---------|----------------|
| 繁體中文+英文 | `['ch_tra', 'en']` |
| 英文 | `['en']` |
| 日文+英文 | `['ja', 'en']` |
| 韓文+英文 | `['ko', 'en']` |

---

## ⚙️ settings.py — 系統設定

**Logger**：`pages.settings`

使用者帳號管理頁面，提供密碼修改、TOTP 驗證器設定與系統資訊查詢。

### 主要功能

| 功能 | 說明 |
|------|------|
| 修改密碼 | 驗證舊密碼後 bcrypt 重新 Hash 儲存 |
| 啟用 TOTP | 產生 QR Code 供 Google Authenticator 掃描，驗證後啟用 |
| 停用 TOTP | 確認後清除 TOTP 秘鑰並停用 2FA |
| 系統資訊 | 顯示 Python 版本、套件版本、GPU 狀態與本機 IP |

### TOTP 設定流程

```
generate_secret()                    # 產生 32 字元 Base32 秘鑰
    ↓
generate_setup_qr_png(secret, user)  # 生成 otpauth:// QR Code PNG
    ↓
[使用者掃描 + 輸入 6 位數驗證碼]
    ↓
verify_code(secret, code)            # 驗證（允許 ±30 秒漂移）
    ↓
save_totp_secret(username, secret)   # 儲存並啟用 TOTP
```

### 側邊欄

此頁面無額外側邊欄參數。
