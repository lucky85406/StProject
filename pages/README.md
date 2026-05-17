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
├── image_upscaler.py     # 🖼 AI 圖像超解析度 + 圖片合併工具
├── image_outpainter.py   # 🪄 AI 直式→橫式轉換（SDXL Outpainting）
├── ocr_scanner.py        # 🔍 OCR 文字辨識（EasyOCR + PDF 批次）
└── settings.py           # ⚙️ 系統設定
```

---

## 🏠 home.py — 系統首頁

**Logger**：`pages.home`

登入後的預設落點頁面，提供系統功能的快速導覽入口。

### 主要內容

- **歡迎橫幅**：顯示登入使用者名稱及當前日期時間
- **功能導覽卡片**（從 `config/pages.py` 的 `HOME_CARDS` 自動生成）
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

### 側邊欄參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| 最大並發數 | Number | 3 | 同時爬取的連結數（1 ~ 10） |
| 請求延遲（秒） | Slider | 1.5 | 每次請求的等待時間（0.5 ~ 5.0） |
| 逾時時間（秒） | Number | 15 | 單頁最長等待時間（5 ~ 60） |
| 最大重試次數 | Number | 3 | 請求失敗後的最大重試次數（0 ~ 10） |
| 遵守 robots.txt | Checkbox | ✅ | 是否遵守目標站 robots.txt 規則 |

---

## 🖼 image_upscaler.py — AI 圖像超解析度 + 圖片合併

**Logger**：`pages.image_upscaler`

以 Tab 切換的影像處理複合頁面：

| Tab | 說明 |
|-----|------|
| 🔬 AI 升解析度工作流 | 節點式 Pipeline，GPU 優先推理 |
| 🖼️ 圖片合併 | 多圖上傳、排列順序控制、水平 / 垂直合併 |

### Tab 1：AI 升解析度工作流

GPU 可用時優先使用 **PyTorch EDSR（GPU bicubic + 銳化卷積）** 進行超解析度推理，無 GPU 時自動降回 **OpenCV DNN**（CPU 備援）。

#### 推理引擎選擇邏輯

```
CUDA 可用（torch.cuda.is_available()）
    └─→ PyTorch GPU 路線：bicubic interpolate + unsharp mask sharpen kernel（無需 .pb 模型）
CUDA 不可用
    └─→ OpenCV DNN（.pb 模型快取於 models/ 目錄，CPU 執行）
```

#### 工作流節點

| 節點 | 圖示 | 引擎 | 說明 |
|------|------|------|------|
| AI 超解析度 | 🔵 | PyTorch / OpenCV DNN | 核心放大推理節點 |
| 雙三次插值升解析度 | 🟣 | PIL BICUBIC | 快速預覽，無需模型 |
| 人像細節強化 | 🟢 | OpenCV + PIL | 銳化、對比、亮度、飽和度、去噪 |
| 人臉銳化（Unsharp Mask） | 🟡 | PIL / OpenCV | 保留皮膚紋理的高頻細節強化 |

#### 支援模型（OpenCV CPU 路線）

| 模型 | 說明 | 可用倍率 |
|------|------|---------|
| **EDSR** | 最高品質，GPU 推薦（預設） | 2× / 3× / 4× |
| **ESPCN** | 速度優先，適合即時場景 | 2× / 3× / 4× |
| **FSRCNN** | 平衡速度與品質 | 2× / 3× / 4× |
| **LapSRN** | 漸進式放大，適合低解析度輸入 | 2× / 4× / 8× |

#### 側邊欄參數

| 參數 | 類型 | 預設值 | 說明 |
|------|------|--------|------|
| AI 模型 | Selectbox | EDSR | EDSR / ESPCN / FSRCNN / LapSRN |
| 放大倍數 | Selectbox | 2× | 2× / 3× / 4× |
| 啟用 GPU 加速 | Checkbox | ✅ | 優先使用 CUDA 推理 |
| 人像細節強化模式 | Checkbox | ☐ | 追加人像後處理節點 |
| 銳化強度 | Slider | 1.2 | 0.0 ~ 3.0，控制全域銳化力道 |

### Tab 2：圖片合併工具

多張圖片上傳後，可自由調整排列順序，合併為水平或垂直排列的單張圖片。

#### 主要功能

| 功能 | 說明 |
|------|------|
| 多圖上傳 | 支援 JPG / PNG / WEBP，2 張以上才可合併 |
| 排列順序控制 | ⬆ / ⬇ 按鈕逐一調整，即時更新預覽編號 |
| 合併方向 | 水平（左右）或垂直（上下） |
| 尺寸對齊 | 以最小邊縮放 / 以最大邊放大 / 不調整三種模式 |
| 下載 | PNG（無損）/ JPEG（壓縮）兩種格式 |

#### 合併邊界保證

```python
# merge_images_combined() 核心邏輯：
# 嚴密相鄰（x += img.width），無縫隙亦無覆蓋
canvas.paste(img, (x, 0))
x += img.width
```

#### 核心函式

| 函式 | 說明 |
|------|------|
| `merge_images_combined(images, direction, scale_mode)` | 合併多張圖片，回傳單張 PIL Image |
| `render_merge_tab()` | 圖片合併工具 Tab 的完整 UI |
| `_render_upscaler_content()` | AI 升解析度工作流 Tab 的完整 UI（內部函式） |
| `show()` | 整合至 app.py 的主入口，以 `st.tabs` 切換兩個 Tab |

#### Session 狀態管理

| Key | 型別 | 說明 |
|-----|------|------|
| `pipeline_nodes` | `list[PipelineNode]` | 目前工作流節點清單 |
| `last_result` | `ProcessingResult` | 最後一次超解析度結果 |
| `merge_result` | `PIL.Image` | 最後一次合併結果 |
| `_merge_file_names` | `list[str]` | 偵測上傳清單變動用 |
| `_merge_order` | `list[int]` | 目前排列順序（原始索引） |

---

## 🪄 image_outpainter.py — AI 直式→橫式轉換

**Logger**：`pages.image_outpainter`

以 **RealVisXL V4 Inpainting（SDXL）** 為底層的 AI Outpainting 頁面，將直式圖片智慧擴展為橫式，透過 cos 漸進式遮罩確保邊緣自然銜接。所有推理邏輯封裝於 `core/outpaint_engine.py`。

### 主要功能

| 功能 | 說明 |
|------|------|
| 直式圖片上傳 | 支援 JPG / PNG / WEBP，自動偵測直橫式並提示 |
| 畫布預覽 | 即時顯示原圖縮放後在橫式畫布中的配置與補全區域 |
| 場景類型選擇 | 5 種內建場景 Preset，大幅改善 AI 補全的空間邏輯 |
| 輔助提示詞 | 可疊加自定義提示詞，與場景 Preset 自動合併 |
| GPU / CPU 自動偵測 | 顯示目前推理裝置與 VRAM 使用量 |
| VRAM 釋放 | 一鍵釋放 Pipeline VRAM，切換其他 AI 功能前使用 |
| 結果對照 | 原圖 vs 結果展開對照，支援 PNG / JPEG 下載 |

### 工作流節點（5 步驟）

```
Node 1：上傳直式圖片（EXIF 旋轉自動修正）
    ↓
Node 2：畫布配置預覽（原圖縮放 + cos 遮罩視覺化）
    ↓
Node 3：場景類型 + 輔助提示詞設定
    ↓
Node 4：執行 AI Outpainting（run_outpaint）
    ↓
Node 5：結果展示 + PNG / JPEG 下載
```

### 場景類型 Preset

| 場景 | 正向提示詞重點 | 負向提示詞重點 |
|------|--------------|--------------|
| 🔍 自動判斷 | 無 | 無 |
| 🪟 室內窗戶 | indoor room, natural light from window | vertical bars, window bars extending |
| 🏠 室內人物 | indoor portrait, warm ambient light, bokeh | outdoor, sky, overexposed |
| 🌿 室外自然 | outdoor natural scenery, open sky | indoor, walls, ceiling |
| 🏙️ 室外城市 | urban cityscape, buildings, architectural continuity | indoor, nature, unrelated elements |

### 側邊欄參數

| 參數 | 類型 | 預設值 | Session Key | 說明 |
|------|------|--------|-------------|------|
| 目標比例 | Selectbox | 16:9 | `outpaint_ratio` | 16:9 / 4:3 / 21:9 / 1:1 |
| 原圖對齊方式 | Selectbox | Middle | `outpaint_align` | Middle / Left / Right |
| 邊緣混合帶（%） | Slider | 10.0 | `outpaint_overlap` | cos 漸進遮罩混合帶寬度 |
| 推理步數 | Number | 30 | `outpaint_steps` | DPMSolver++ 步數（建議 20~30） |

### Session 狀態管理

| Key | 型別 | 說明 |
|-----|------|------|
| `outpaint_result` | `PIL.Image` | 最後一次 Outpainting 結果，重新執行前自動清除 |

### 推理規格

| 項目 | 規格 |
|------|------|
| 基礎模型 | `OzzyGT/RealVisXL_V4.0_inpainting`（首次執行自動下載，約 6~8 GB） |
| VAE | `madebyollin/sdxl-vae-fp16-fix` |
| Scheduler | DPMSolver++（sde）+ Karras Sigmas |
| Guidance Scale | 5.0（固定） |
| Strength | 1.0（完整補全，固定） |
| GPU 耗時 | 約 15~60 秒（依 GPU 效能） |
| CPU 耗時 | 30~60 分鐘（不建議） |

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

### 側邊欄參數

| 參數 | 類型 | 預設值 | Session Key | 說明 |
|------|------|--------|-------------|------|
| 辨識語言 | Selectbox | 繁體中文+英文 | `ocr_lang` | 傳入 EasyOCR 語言代碼 |
| 最低信心度 | Slider | 0.5 | `ocr_confidence` | 低於此值的結果將被過濾 |
| 啟用圖像預處理 | Checkbox | ✅ | `ocr_preprocess` | 高斯去噪是否啟用 |
| 啟用傾斜校正 | Checkbox | ✅ | `ocr_deskew` | 霍夫直線 Deskew |
| 啟用 GPU | Checkbox | ✅ | `ocr_gpu` | EasyOCR GPU 推理 |
| PDF DPI | Selectbox | 200 DPI | `ocr_pdf_dpi` | PDF 頁面渲染解析度 |

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
| 設備管理 | 查詢 / 刪除已綁定設備的 device hash 記錄 |
| 系統資訊 | 顯示 Python 版本、套件版本、GPU 狀態與本機 IP |

### 側邊欄

此頁面無額外側邊欄參數。
