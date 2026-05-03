# 🧩 core/ — 核心業務邏輯模組

本目錄包含 StProject 所有共用核心邏輯，涵蓋資料庫連線、身份驗證、Session 管理、TOTP、QR 登入、消費記錄資料存取層與 OCR 推理引擎。

> **設計原則**：所有模組均採用標準 Python `logging`，**不直接依賴 Streamlit**（`db.py` 除外，用於讀取 `st.secrets`），可獨立進行單元測試。

---

## 目錄結構

```
core/
├── auth.py           # Auth 公開介面（re-export session_store）
├── db.py             # Supabase 連線工廠（lru_cache 單例）
├── expense_db.py     # 消費記錄 DAL（v2：user_id 多使用者隔離）
├── network.py        # 網路工具（取得本機 IP）
├── ocr_engine.py     # OCR 推理引擎（EasyOCR 封裝 + 圖像預處理 Pipeline）
├── qr_login.py       # QR Code 圖片產生與確認 URL 建構
├── qr_store.py       # QR Token 狀態機（JSON 檔案儲存）
├── session_store.py  # 登入 Session 建立 / 驗證 / 刪除
├── totp.py           # Google Authenticator TOTP 工具（RFC 6238）
└── users.py          # 使用者帳號驗證與管理
```

---

## 🔌 db.py — Supabase 連線工廠

Supabase 客戶端的單例工廠，整個 App 生命週期只初始化一次。

```python
from core.db import get_client

client = get_client()  # 回傳快取的 supabase.Client
```

**實作細節**：
- 使用 `@lru_cache(maxsize=1)` 確保連線不重複建立
- 憑證從 `st.secrets["supabase"]` 讀取（`.streamlit/secrets.toml`）
- 使用 **service_role** key，繞過 Row Level Security（RLS），適合伺服器端操作
- Supabase Python Client 為執行緒安全，在 Streamlit 多執行緒環境下可正常運作

### 必要 Secrets 設定

```toml
# .streamlit/secrets.toml
[supabase]
url = "https://xxxxxxxxxxxx.supabase.co"
service_key = "eyJ..."
```

---

## 👤 users.py — 使用者帳號管理

提供所有帳號相關操作，對接 Supabase `users` 資料表。

### 主要函式

| 函式 | 回傳值 | 說明 |
|------|--------|------|
| `verify_login(username, password, totp_code)` | `tuple[bool, LoginReason]` | 統一登入驗證入口 |
| `verify_password(username, password)` | `bool` | 僅驗證密碼（bcrypt checkpw） |
| `user_exists(username)` | `bool` | 確認使用者是否存在（QR 登入用） |
| `get_user_id(username)` | `str \| None` | 取得使用者 UUID（消費記錄隔離用） |
| `create_user(username, password)` | `bool` | 新增使用者，TOTP 預設停用 |
| `change_password(username, old_pw, new_pw)` | `bool` | 修改密碼（驗證舊密碼後 bcrypt 重新 Hash） |
| `get_totp_info(username)` | `tuple[bool, str \| None]` | 取得 `(totp_enabled, totp_secret)` |
| `save_totp_secret(username, secret)` | `bool` | 儲存 TOTP 秘鑰並啟用 |
| `disable_totp(username)` | `bool` | 清除 TOTP 秘鑰並停用 |

### bcrypt 密碼規格

- Hash 演算法：`bcrypt`，`rounds=12`
- 驗證：`bcrypt.checkpw(password.encode(), stored_hash)`

---

## 🔐 session_store.py — Session 管理

登入 Session 的生命週期管理，所有 Token 儲存於 Supabase `sessions` 資料表。

### 主要函式

| 函式 | 回傳值 | 說明 |
|------|--------|------|
| `create_session(username)` | `str` | 建立 UUID Session Token，預設有效期 24 小時 |
| `verify_session(token)` | `str \| None` | 驗證 Token 並回傳 username，過期則回傳 None |
| `delete_session(token)` | `bool` | 登出時刪除 Session |

---

## 🔑 auth.py — Auth 公開介面

`session_store` 的重新匯出（re-export）模組，提供統一的 Auth 入口，避免頁面直接依賴 `session_store`。

```python
from core.auth import create_session, verify_session, delete_session
```

---

## 🔢 totp.py — TOTP 雙因素驗證

Google Authenticator 相容的 TOTP 實作，基於 `pyotp` 套件，遵循 RFC 6238 標準。

### 主要函式

| 函式 | 回傳值 | 說明 |
|------|--------|------|
| `generate_secret()` | `str` | 產生 32 字元 Base32 隨機秘鑰 |
| `get_provisioning_uri(secret, username, issuer)` | `str` | 產生 `otpauth://` URI |
| `generate_setup_qr_png(secret, username)` | `bytes` | 產生 TOTP 設定 QR Code（PNG bytes） |
| `verify_code(secret, code)` | `bool` | 驗證 6 位數 TOTP 碼 |

### 驗證時間容許度

`verify_code()` 使用 `valid_window=1`，允許前後各 30 秒的時鐘漂移，有效窗口共 **90 秒**。

```python
from core.totp import generate_secret, generate_setup_qr_png, verify_code

secret = generate_secret()
qr_png = generate_setup_qr_png(secret, "admin")  # 回傳 PNG bytes → st.image()
is_valid = verify_code(secret, "123456")
```

---

## 📷 qr_login.py — QR Code 登入工具

產生供手機掃描的登入 QR Code 圖片，以及用於後端確認的 URL。

### 主要函式

| 函式 | 回傳值 | 說明 |
|------|--------|------|
| `generate_qr_image(token, base_url)` | `bytes` | 產生 QR Code PNG（內含確認 URL） |
| `build_confirm_url(token, base_url)` | `str` | 建構 `?action=confirm_qr&token=<token>` URL |

---

## 🎫 qr_store.py — QR Token 狀態機

QR Code 登入流程的 Token 生命週期管理，使用本地 JSON 檔案作為暫存儲存（適合單機部署）。

### Token 狀態

```
pending → confirmed → consumed（正常流程）
pending → expired（Token 超過有效期未使用）
```

### 主要函式

| 函式 | 回傳值 | 說明 |
|------|--------|------|
| `create_qr_token()` | `str` | 建立新的 pending Token（UUID） |
| `check_qr_token(token)` | `str` | 回傳目前狀態：`pending / confirmed / expired` |
| `confirm_qr_token(token, username)` | `bool` | 手機掃描後確認 Token（綁定 username） |
| `consume_qr_token(token)` | `str \| None` | 消費 Token，回傳綁定的 username |

---

## 💾 expense_db.py — 消費記錄資料存取層（v2）

消費記錄功能的資料存取層（DAL），所有函式均以 `user_id`（UUID）作為必要參數，確保多使用者資料隔離。

### Pydantic 資料模型

```python
class Category(BaseModel):
    id: str
    name: str
    icon: str
    is_default: bool
    sort_order: int
    user_id: str | None  # None = 全域預設

class Expense(BaseModel):
    id: str
    user_id: str
    amount: Decimal
    category_id: str
    note: str | None
    date: date
    created_at: datetime

class TodaySummary(BaseModel):
    total: Decimal
    count: int
    items: list[Expense]
```

### 主要函式

| 函式 | 說明 |
|------|------|
| `get_all_categories(user_id)` | 合併全域預設 + 使用者自訂類別，依 sort_order 排序 |
| `add_expense(user_id, amount, category_id, note, date)` | 新增消費記錄 |
| `get_today_summary(user_id)` | 取得今日消費總覽 |
| `get_expenses(user_id, start, end, category_id)` | 依條件查詢歷史消費記錄 |
| `get_expense_by_id(expense_id)` | 依 ID 取得單筆記錄 |
| `update_expense(expense_id, amount, category_id, note)` | 更新消費記錄 |
| `soft_delete_expense(expense_id)` | 軟刪除（設定 `deleted_at`，不實際移除） |

---

## 🔍 ocr_engine.py — OCR 推理引擎

EasyOCR 的封裝模組，提供圖像預處理 Pipeline 與文字辨識功能。**不依賴 Streamlit**，可獨立進行單元測試。

### 主要函式

| 函式 | 回傳值 | 說明 |
|------|--------|------|
| `load_file_as_images(file_bytes, file_name, pdf_dpi, max_pdf_pages)` | `list[PIL.Image]` | 將上傳的 PDF 或圖片統一轉為 PIL Image 列表 |
| `preprocess_image(pil_img, denoise, binarize, deskew)` | `np.ndarray` | 圖像預處理 Pipeline（輸出 OpenCV BGR ndarray） |
| `run_ocr(cv_img, lang_key, use_gpu, min_confidence)` | `list[dict]` | 執行 EasyOCR 辨識並篩選信心度 |
| `post_process(raw_results)` | `tuple[str, list[dict]]` | 排序結果並合併全文字串 |

### 圖像預處理 Pipeline

```python
preprocess_image(pil_img, denoise=True, binarize=False, deskew=True)
```

| 步驟 | 函式 / 演算法 | 說明 |
|------|-------------|------|
| 1. 轉灰階 | `cv2.COLOR_RGB2GRAY` | RGB → 灰階 |
| 2. 高斯去噪 | `cv2.GaussianBlur(3×3)` | 去除感光元件噪點（可選） |
| 3. 二值化 | `cv2.THRESH_OTSU` | 大津演算法自動閾值（可選） |
| 4. 傾斜校正 | 霍夫直線偵測（Hough Transform） | 修正 ±15° 以內的歪斜 |
| 5. 回傳 BGR | `cv2.COLOR_GRAY2BGR` | EasyOCR 接受 3 通道 BGR |

### PDF 解析規格

| 參數 | 值 | 說明 |
|------|----|------|
| 引擎 | `PyMuPDF（fitz）` | 高效能 PDF 渲染 |
| 預設 DPI | 200 | 渲染矩陣：`dpi / 72` |
| 最多頁數 | 10 | 避免大型 PDF 佔用過多記憶體 |
| 色彩空間 | `RGB` | 透過 `fitz.csRGB` 指定 |

```python
from core.ocr_engine import load_file_as_images, preprocess_image

images = load_file_as_images(file_bytes, "document.pdf", pdf_dpi=200)
cv_img = preprocess_image(images[0], denoise=True, deskew=True)
```

### EasyOCR Reader 快取

EasyOCR 的 `Reader` 物件初始化耗時較長（需下載語言模型）。`run_ocr()` 內部以 `@st.cache_resource` 快取 Reader 實例，相同語言組合僅初始化一次。

> ⚠️ 若需在非 Streamlit 環境使用，請自行管理 Reader 快取（例如使用 `functools.lru_cache`）。

### 結果資料結構

```python
# raw_results 單筆格式（來自 EasyOCR）
{
    "bbox": [[x1,y1], [x2,y1], [x2,y2], [x1,y2]],  # 四個角點座標
    "text": "辨識文字",
    "confidence": 0.9823
}
```

---

## 🌐 network.py — 網路工具

提供本機 IP 查詢功能，用於 `settings.py` 的系統資訊面板。

```python
from core.network import get_local_ip

ip = get_local_ip()  # 回傳本機 IP 字串，例如 "192.168.1.100"
```

---

## 📐 模組依賴關係

```
app.py
 ├─ core.session_store  (create_session, verify_session, delete_session)
 ├─ core.users          (verify_password, get_user_id)
 ├─ core.qr_store       (create_qr_token, check_qr_token, consume_qr_token, confirm_qr_token)
 └─ core.qr_login       (generate_qr_image, build_confirm_url)

pages/daily_expense.py
 ├─ core.expense_db     (所有 DAL 函式)
 └─ core.users          (get_user_id)

pages/settings.py
 ├─ core.users          (change_password, get_totp_info, save_totp_secret, disable_totp)
 ├─ core.totp           (generate_secret, generate_setup_qr_png, verify_code)
 └─ core.network        (get_local_ip)

pages/ocr_scanner.py
 └─ core.ocr_engine     (load_file_as_images, preprocess_image, run_ocr, post_process)

所有 core/* (需要資料庫)
 └─ core.db             (get_client)
```
