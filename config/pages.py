# config/pages.py
"""
頁面總設定檔 — Single Source of Truth
────────────────────────────────────────────────────────────────
每新增一個功能頁只需在此檔案的 PAGE_CONFIG 尾端追加一個 dict，
app.py（側欄導覽 + Hero）與 pages/home.py（首頁卡片）會自動
取用，無需修改其他檔案。

必填欄位
  id            str   路由識別碼，需與 pages/ 目錄下的模組對應
  icon          str   Emoji 圖示
  label         str   側欄導覽短標籤（≤ 4 字）
  title         str   頁面 Hero 標題 / 首頁卡片標題
  subtitle      str   頁面 Hero 副標題
  desc          str   首頁卡片說明文字（1–2 句）
  accent        str   首頁卡片主色（CSS color）
  accent_soft   str   首頁卡片背景色（低不透明度）
  border_soft   str   首頁卡片邊框色（低不透明度）
  module        str   Python import 路徑，供 importlib 動態載入
  show_in_home  bool  是否顯示於首頁快速導覽卡片
  params        list  Sidebar 功能參數面板定義（空清單 = 不顯示）

params 每個元素為 dict，type 可為：
  selectbox | checkbox | slider | number
"""
from __future__ import annotations

from typing import Any

PAGE_CONFIG: list[dict[str, Any]] = [
    # ── 首頁 ────────────────────────────────────────────────────────
    {
        "id": "home",
        "icon": "🏠",
        "label": "首頁",
        "title": "系統首頁",
        "subtitle": "歡迎使用 Bllln Web 管理平台",
        "desc": "系統總覽、快速導覽與最新消息",
        "accent": "#7c6ff7",
        "accent_soft": "rgba(124,111,247,0.10)",
        "border_soft": "rgba(124,111,247,0.20)",
        "module": "pages.home",
        "show_in_home": False,  # 首頁本身不在卡片中顯示
        "params": [],
    },
    # ── 每日消費 ─────────────────────────────────────────────────────
    {
        "id": "daily_expense",
        "icon": "💰",
        "label": "消費",
        "title": "每日消費記錄",
        "subtitle": "快速記帳 · 今日總覽 · 預算追蹤",
        "desc": "快速記帳、預算追蹤與多類別管理",
        "accent": "#10b981",
        "accent_soft": "rgba(16,185,129,0.10)",
        "border_soft": "rgba(16,185,129,0.20)",
        "module": "pages.daily_expense",
        "show_in_home": True,
        "params": [],
    },
    # ── 儀表板 ───────────────────────────────────────────────────────
    {
        "id": "dashboard",
        "icon": "📊",
        "label": "儀表板",
        "title": "資料儀表板",
        "subtitle": "圖表分析與關鍵指標總覽",
        "desc": "趨勢圖表、時間維度分析與資料視覺化",
        "accent": "#6c8eff",
        "accent_soft": "rgba(108,142,255,0.10)",
        "border_soft": "rgba(108,142,255,0.22)",
        "module": "pages.dashboard",
        "show_in_home": True,
        "params": [
            {
                "type": "selectbox",
                "key": "dash_range",
                "label": "時間範圍",
                "options": ["最近 7 天", "最近 30 天", "最近 90 天", "本年度"],
                "default": 0,
            },
            {
                "type": "selectbox",
                "key": "dash_chart",
                "label": "圖表類型",
                "options": ["折線圖", "長條圖", "面積圖"],
                "default": 0,
            },
            {
                "type": "checkbox",
                "key": "dash_animate",
                "label": "啟用動態效果",
                "default": True,
            },
        ],
    },
    # ── 網頁爬蟲 ─────────────────────────────────────────────────────
    {
        "id": "crawler",
        "icon": "🕸",
        "label": "爬蟲",
        "title": "網頁爬蟲工作台",
        "subtitle": "資料搜集、彙整分析與二階段 Pipeline",
        "desc": "兩階段 Pipeline、自動偵測商品與影片頁",
        "accent": "#f59e0b",
        "accent_soft": "rgba(245,158,11,0.10)",
        "border_soft": "rgba(245,158,11,0.22)",
        "module": "pages.crawler_dashboard",
        "show_in_home": True,
        "params": [
            {
                "type": "number",
                "key": "crawl_concurrency",
                "label": "最大並發數",
                "min": 1,
                "max": 10,
                "default": 3,
            },
            {
                "type": "slider",
                "key": "crawl_delay",
                "label": "請求延遲 (秒)",
                "min": 0.5,
                "max": 5.0,
                "step": 0.5,
                "default": 1.5,
            },
            {
                "type": "number",
                "key": "crawl_timeout",
                "label": "逾時時間 (秒)",
                "min": 5,
                "max": 60,
                "default": 15,
            },
            {
                "type": "number",
                "key": "crawl_retries",
                "label": "最大重試次數",
                "min": 0,
                "max": 10,
                "default": 3,
            },
            {
                "type": "checkbox",
                "key": "crawl_robots",
                "label": "遵守 robots.txt",
                "default": True,
            },
        ],
    },
    # ── AI 超解析度 ──────────────────────────────────────────────────
    {
        "id": "upscaler",
        "icon": "🖼",
        "label": "超解析度",
        "title": "AI 圖像超解析度",
        "subtitle": "GPU 加速 · PyTorch EDSR · 人像細節強化",
        "desc": "GPU/CPU 自動切換，EDSR 模型放大推理",
        "accent": "#e879a0",
        "accent_soft": "rgba(232,121,160,0.10)",
        "border_soft": "rgba(232,121,160,0.22)",
        "module": "pages.image_upscaler",
        "show_in_home": True,
        "params": [
            {
                "type": "selectbox",
                "key": "up_model",
                "label": "AI 模型",
                "options": ["EDSR", "ESPCN", "FSRCNN", "LapSRN"],
                "default": 0,
            },
            {
                "type": "selectbox",
                "key": "up_scale",
                "label": "放大倍數",
                "options": ["2×", "3×", "4×"],
                "default": 0,
            },
            {
                "type": "checkbox",
                "key": "up_gpu",
                "label": "啟用 GPU 加速",
                "default": True,
            },
            {
                "type": "checkbox",
                "key": "up_portrait",
                "label": "人像細節強化模式",
                "default": False,
            },
            {
                "type": "slider",
                "key": "up_sharpen",
                "label": "銳化強度",
                "min": 0.0,
                "max": 3.0,
                "step": 0.1,
                "default": 1.2,
            },
        ],
    },
    # ── OCR 文字辨識 ──────────────────────────────────────────────────
    {
        "id": "ocr_scanner",
        "icon": "🔍",
        "label": "OCR",
        "title": "OCR 文字辨識",
        "subtitle": "圖像文字提取 · 多語言支援 · PDF 批次解析",
        "desc": "圖像文字提取 · 多語言支援 · PDF 批次解析",
        "accent": "#4982A6",
        "accent_soft": "rgba(73,130,166,0.10)",
        "border_soft": "rgba(73,130,166,0.22)",
        "module": "pages.ocr_scanner",
        "show_in_home": True,
        "params": [
            {
                "type": "selectbox",
                "key": "ocr_lang",
                "label": "辨識語言",
                "options": ["繁體中文+英文", "英文", "日文+英文", "韓文+英文"],
                "default": 0,
            },
            {
                "type": "slider",
                "key": "ocr_confidence",
                "label": "最低信心度",
                "min": 0.1,
                "max": 1.0,
                "step": 0.05,
                "default": 0.5,
            },
            {
                "type": "checkbox",
                "key": "ocr_preprocess",
                "label": "啟用圖像預處理",
                "default": True,
            },
            {
                "type": "checkbox",
                "key": "ocr_deskew",
                "label": "自動傾斜校正",
                "default": True,
            },
            {
                "type": "checkbox",
                "key": "ocr_gpu",
                "label": "啟用 GPU 加速",
                "default": True,
            },
            {
                "type": "selectbox",
                "key": "ocr_pdf_dpi",
                "label": "PDF 渲染 DPI",
                "options": ["150 DPI", "200 DPI", "300 DPI"],
                "default": 1,
            },
        ],
    },
    # ── 系統設定 ─────────────────────────────────────────────────────
    {
        "id": "settings",
        "icon": "⚙️",
        "label": "設定",
        "title": "系統設定",
        "subtitle": "個人資料、密碼修改與外觀偏好",
        "desc": "帳號管理、TOTP 驗證器與外觀偏好",
        "accent": "#8b85a8",
        "accent_soft": "rgba(139,133,168,0.10)",
        "border_soft": "rgba(139,133,168,0.22)",
        "module": "pages.settings",
        "show_in_home": True,
        "params": [],
    },
    # ════════════════════════════════════════════════════════════════
    # 新增功能頁範本（複製貼上後修改即可）
    # ════════════════════════════════════════════════════════════════
    # {
    #     "id":           "new_feature",          # 路由 id（英文小寫+底線）
    #     "icon":         "🆕",
    #     "label":        "新功能",               # 側欄短標籤 ≤ 4 字
    #     "title":        "新功能標題",
    #     "subtitle":     "Hero 副標題",
    #     "desc":         "首頁卡片說明（1–2句）",
    #     "accent":       "#06b6d4",
    #     "accent_soft":  "rgba(6,182,212,0.10)",
    #     "border_soft":  "rgba(6,182,212,0.22)",
    #     "module":       "pages.new_feature",    # 對應 pages/new_feature.py
    #     "show_in_home": True,
    #     "params":       [],                     # 若有側欄參數則填入
    # },
]

# ── 衍生資料（供各模組直接 import 使用）────────────────────────────
PAGE_MAP: dict[str, dict] = {p["id"]: p for p in PAGE_CONFIG}

# 僅出現在首頁卡片的頁面清單
HOME_CARDS: list[dict] = [p for p in PAGE_CONFIG if p.get("show_in_home")]
