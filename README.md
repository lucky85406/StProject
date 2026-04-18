# StProject

基於 Streamlit 的 Web 應用，包含登入驗證與多頁面架構。

## 專案結構

```
StProject/
├── app.py                  # 主程式入口（登入 + 路由）
├── pages/
│   ├── __init__.py
│   ├── home.py             # 首頁
│   ├── dashboard.py        # 儀表板
│   └── settings.py         # 設定
├── .streamlit/
│   └── config.toml         # Streamlit 設定
├── pyproject.toml
└── uv.lock
```

## 快速開始

### 1. 安裝相依套件（使用 uv）

```bash
uv sync
```

### 2. 啟動應用

```bash
uv run streamlit run app.py
```

### 3. 開啟瀏覽器

前往 http://localhost:8501

## 測試帳號

| 帳號    | 密碼       |
|---------|-----------|
| admin   | admin123  |
| user    | user123   |

## 功能說明

- **登入畫面**：帳號密碼驗證，登入失敗顯示錯誤提示
- **首頁**：顯示指標卡片與最新消息
- **儀表板**：折線圖與長條圖示範
- **設定**：個人資料、密碼修改、外觀偏好
- **登出**：清除 session，返回登入畫面
