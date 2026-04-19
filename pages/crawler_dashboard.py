"""
網頁爬蟲功能頁面 - crawler_dashboard.py
放置路徑：pages/crawler_dashboard.py
用途：資料搜集與彙整分析（商品名稱/連結/影片名稱/標籤）
限制：僅供內部分析，不進行商業使用及二次上傳
"""

import asyncio
import re
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import httpx
import streamlit as st
import pandas as pd
from selectolax.parser import HTMLParser
from pydantic import BaseModel, field_validator

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════
#  資料模型
# ════════════════════════════════════════════════════════


class ContentType(str, Enum):
    PRODUCT = "商品"
    VIDEO = "影片"
    UNKNOWN = "未知"


class CollectedItem(BaseModel):
    """
    任務專屬資料模型
    僅收集：名稱、連結、標籤 — 不儲存個人資料
    purpose: internal_analysis_only
    """

    content_type: ContentType = ContentType.UNKNOWN
    name: str = ""
    url: str = ""
    tags: list[str] = []
    thumbnail_url: Optional[str] = None
    source_platform: str = ""
    fetch_time_ms: int = 0
    error: Optional[str] = None

    @field_validator("url")
    @classmethod
    def block_private_ip(cls, v: str) -> str:
        import ipaddress

        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("僅允許 http/https")
        hostname = parsed.hostname or ""
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValueError(f"禁止存取內網位址: {hostname}")
        except ValueError as e:
            if "禁止" in str(e):
                raise
        return v


# 確保 Pydantic v2 正確解析所有型別（model_rebuild 強制重新解析 forward references）
CollectedItem.model_rebuild()


@dataclass
class CrawlerConfig:
    max_concurrency: int = 3
    request_delay: float = 1.5
    timeout: float = 15.0
    max_retries: int = 3
    respect_robots: bool = True
    purpose: str = "internal_analysis_only"
    headers: dict[str, str] = field(
        default_factory=lambda: {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )


# ════════════════════════════════════════════════════════
#  平台偵測與解析策略
# ════════════════════════════════════════════════════════


def detect_platform(url: str) -> tuple[ContentType, str]:
    """根據 URL 自動偵測平台類型"""
    hostname = urlparse(url).netloc.lower()
    platform_map = {
        # 電商平台
        "shopee.tw": (ContentType.PRODUCT, "蝦皮購物"),
        "shopee.com": (ContentType.PRODUCT, "蝦皮購物"),
        "pchome.com.tw": (ContentType.PRODUCT, "PChome"),
        "momo.com.tw": (ContentType.PRODUCT, "momo購物"),
        "books.com.tw": (ContentType.PRODUCT, "博客來"),
        "amazon.com": (ContentType.PRODUCT, "Amazon"),
        # 影片平台
        "youtube.com": (ContentType.VIDEO, "YouTube"),
        "youtu.be": (ContentType.VIDEO, "YouTube"),
        "bilibili.com": (ContentType.VIDEO, "Bilibili"),
        "vimeo.com": (ContentType.VIDEO, "Vimeo"),
        "twitch.tv": (ContentType.VIDEO, "Twitch"),
    }
    for domain, info in platform_map.items():
        if domain in hostname:
            return info
    return (ContentType.UNKNOWN, hostname)


def parse_product(tree: HTMLParser, url: str, platform: str) -> CollectedItem:
    """電商商品資訊解析"""
    name = ""
    tags: list[str] = []
    thumbnail_url = None

    # 通用商品名稱選擇器（依優先序）
    name_selectors = [
        "h1.pdp-mod-product-badge-title",  # Shopee
        "h1.product-title",
        "[class*='product-name']",
        "[class*='item-title']",
        "[class*='product_name']",
        "h1",
    ]
    for sel in name_selectors:
        node = tree.css_first(sel)
        if node and node.text(strip=True):
            name = node.text(strip=True)[:200]
            break

    # 標籤/關鍵字
    meta_keywords = tree.css_first('meta[name="keywords"]')
    if meta_keywords:
        kw = meta_keywords.attributes.get("content", "")
        tags = [t.strip() for t in kw.split(",") if t.strip()][:10]

    # 補充：麵包屑作為分類標籤
    breadcrumbs = tree.css("[class*='breadcrumb'] a, [class*='crumb'] a")
    for bc in breadcrumbs[:3]:
        bc_text = bc.text(strip=True)
        if bc_text and bc_text not in tags:
            tags.append(bc_text)

    # 縮圖
    og_img = tree.css_first('meta[property="og:image"]')
    if og_img:
        thumbnail_url = og_img.attributes.get("content")

    # 若無名稱，嘗試 og:title
    if not name:
        og_title = tree.css_first('meta[property="og:title"]')
        if og_title:
            name = og_title.attributes.get("content", "")[:200]

    return CollectedItem(
        content_type=ContentType.PRODUCT,
        name=name or "（未能取得商品名稱）",
        url=url,
        tags=tags,
        thumbnail_url=thumbnail_url,
        source_platform=platform,
    )


def parse_video(tree: HTMLParser, url: str, platform: str) -> CollectedItem:
    """影片資訊解析"""
    name = ""
    tags: list[str] = []
    thumbnail_url = None

    # og:title 是影片平台最可靠的標題來源
    og_title = tree.css_first('meta[property="og:title"]')
    if og_title:
        name = og_title.attributes.get("content", "")[:200]

    if not name:
        title_node = tree.css_first("title")
        if title_node:
            name = title_node.text(strip=True)[:200]

    # 影片標籤 (YouTube / Bilibili)
    tag_selectors = [
        'meta[name="keywords"]',
        'meta[property="og:video:tag"]',
    ]
    for sel in tag_selectors:
        nodes = tree.css(sel)
        for node in nodes:
            content = node.attributes.get("content", "")
            tags += [t.strip() for t in content.split(",") if t.strip()]

    tags = list(dict.fromkeys(tags))[:15]  # 去重，最多15個

    # 縮圖
    og_img = tree.css_first('meta[property="og:image"]')
    if og_img:
        thumbnail_url = og_img.attributes.get("content")

    return CollectedItem(
        content_type=ContentType.VIDEO,
        name=name or "（未能取得影片名稱）",
        url=url,
        tags=tags,
        thumbnail_url=thumbnail_url,
        source_platform=platform,
    )


def parse_generic(
    tree: HTMLParser, url: str, platform: str, content_type: ContentType
) -> CollectedItem:
    """通用解析（自動偵測模式）"""
    if content_type == ContentType.PRODUCT:
        return parse_product(tree, url, platform)
    elif content_type == ContentType.VIDEO:
        return parse_video(tree, url, platform)

    # 完全未知：取 og:title + keywords
    name = ""
    og_title = tree.css_first('meta[property="og:title"]')
    if og_title:
        name = og_title.attributes.get("content", "")[:200]
    if not name:
        h1 = tree.css_first("h1")
        if h1:
            name = h1.text(strip=True)[:200]

    meta_kw = tree.css_first('meta[name="keywords"]')
    tags = []
    if meta_kw:
        tags = [
            t.strip()
            for t in meta_kw.attributes.get("content", "").split(",")
            if t.strip()
        ][:10]

    return CollectedItem(
        content_type=ContentType.UNKNOWN,
        name=name or "（未知）",
        url=url,
        tags=tags,
        source_platform=platform,
    )


# ════════════════════════════════════════════════════════
#  爬蟲核心
# ════════════════════════════════════════════════════════


def check_robots_allowed(url: str) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
        return rp.can_fetch("*", url)
    except Exception:
        return True


async def fetch_one(
    client: httpx.AsyncClient,
    url: str,
    config: CrawlerConfig,
    semaphore: asyncio.Semaphore,
) -> CollectedItem:
    """爬取單一 URL"""
    start = time.monotonic()
    content_type, platform = detect_platform(url)

    for attempt in range(config.max_retries):
        try:
            async with semaphore:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()

            tree = HTMLParser(resp.text)
            # 移除雜訊
            for tag in tree.css("script, style, noscript"):
                tag.decompose()

            item = parse_generic(tree, url, platform, content_type)
            item.fetch_time_ms = int((time.monotonic() - start) * 1000)
            return item

        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code in (403, 404, 410):
                return CollectedItem(
                    url=url,
                    source_platform=platform,
                    error=f"HTTP {code}",
                    fetch_time_ms=int((time.monotonic() - start) * 1000),
                )
            await asyncio.sleep(config.request_delay * (2**attempt))

        except Exception as e:
            await asyncio.sleep(config.request_delay * (attempt + 1))
            last_error = str(e)

    return CollectedItem(
        url=url,
        source_platform=platform,
        error=f"失敗（重試 {config.max_retries} 次）",
        fetch_time_ms=int((time.monotonic() - start) * 1000),
    )


async def run_crawl_async(
    urls: list[str], config: CrawlerConfig
) -> list[CollectedItem]:
    """非同步批量爬取主函式"""
    if config.respect_robots:
        allowed = [u for u in urls if check_robots_allowed(u)]
        blocked = len(urls) - len(allowed)
        if blocked > 0:
            st.warning(f"⚠️ {blocked} 個 URL 被 robots.txt 封鎖，已自動跳過。")
        urls = allowed

    if not urls:
        return []

    semaphore = asyncio.Semaphore(config.max_concurrency)
    results: list[CollectedItem] = []

    async with httpx.AsyncClient(
        headers=config.headers,
        timeout=config.timeout,
        http2=True,
        follow_redirects=True,
    ) as client:
        tasks = [fetch_one(client, url, config, semaphore) for url in urls]
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            item = await coro
            results.append(item)
            await asyncio.sleep(config.request_delay)

    return results


def run_crawl(urls: list[str], config: CrawlerConfig) -> list[CollectedItem]:
    """Streamlit 同步包裝器"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(run_crawl_async(urls, config))
    finally:
        loop.close()


# ════════════════════════════════════════════════════════
#  Streamlit UI
# ════════════════════════════════════════════════════════


def _inject_styles() -> None:
    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap');

    :root {
        /* ── 柔和漸層色系 ── */
        --bg:        #f0f4ff;
        --bg-end:    #faf5ff;
        --surface:   rgba(255,255,255,0.72);
        --surface2:  rgba(255,255,255,0.50);
        --border:    rgba(148,130,210,0.18);
        --border2:   rgba(168,148,228,0.28);

        /* 主色：薰衣草紫 → 玫瑰粉 漸層 */
        --accent:    #8b5cf6;
        --accent2:   #ec4899;
        --accent-soft: rgba(139,92,246,0.12);

        /* 功能色 */
        --success:   #059669;
        --warn:      #d97706;
        --danger:    #dc2626;

        /* 文字 */
        --text:      #1e1b4b;
        --text2:     #4c1d95;
        --muted:     #7c6fa0;

        /* 尺寸 */
        --radius:    14px;

        /* 漸層捷徑 */
        --grad-main:  linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%);
        --grad-soft:  linear-gradient(135deg, rgba(139,92,246,0.15) 0%, rgba(236,72,153,0.10) 100%);
        --grad-bg:    linear-gradient(160deg, #f0f4ff 0%, #faf0ff 50%, #fff5f8 100%);
        --grad-sidebar: linear-gradient(180deg, #f5f0ff 0%, #fdf4ff 100%);
    }

    html, body, [data-testid="stAppViewContainer"] {
        background: var(--grad-bg) !important;
        background-attachment: fixed !important;
        color: var(--text) !important;
        font-family: 'Syne', sans-serif;
    }

    /* 主內容區帶微妙紋理 */
    [data-testid="stAppViewContainer"] > section {
        background: transparent !important;
    }
    [data-testid="stMain"] {
        background: transparent !important;
    }

    /* 隱藏 Streamlit 預設元素 */
    #MainMenu, footer { visibility: hidden; }
    /* header 保留顯示，確保頂部 Rerun 按鈕與設定齒輪可正常使用 */
    [data-testid="stSidebar"] {
        background: var(--grad-sidebar) !important;
        border-right: 1px solid var(--border2) !important;
        box-shadow: 2px 0 20px rgba(139,92,246,0.06) !important;
    }
    [data-testid="stSidebar"] > div {
        background: transparent !important;
    }

    /* 頁面標題區 */
    .hero-header {
        background: linear-gradient(135deg,
            rgba(139,92,246,0.10) 0%,
            rgba(236,72,153,0.07) 50%,
            rgba(255,255,255,0.80) 100%);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid var(--border2);
        border-radius: var(--radius);
        padding: 2rem 2.5rem;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 24px rgba(139,92,246,0.08);
    }
    .hero-header::before {
        content: '';
        position: absolute;
        top: -70px; right: -50px;
        width: 240px; height: 240px;
        background: radial-gradient(circle,
            rgba(139,92,246,0.18) 0%, transparent 68%);
        border-radius: 50%;
    }
    .hero-header::after {
        content: '';
        position: absolute;
        bottom: -50px; left: 25%;
        width: 200px; height: 200px;
        background: radial-gradient(circle,
            rgba(236,72,153,0.14) 0%, transparent 68%);
        border-radius: 50%;
    }
    .hero-title {
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        background: var(--grad-main);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0 0 0.4rem 0;
    }
    .hero-sub {
        color: var(--muted);
        font-size: 0.875rem;
        font-family: 'DM Mono', monospace;
        margin: 0;
    }
    .compliance-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: linear-gradient(90deg, rgba(5,150,105,0.10), rgba(139,92,246,0.08));
        border: 1px solid rgba(5,150,105,0.25);
        color: #059669;
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.75rem;
        font-family: 'DM Mono', monospace;
        margin-top: 0.75rem;
    }

    /* 統計卡片 */
    .stat-grid {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
        margin-bottom: 1.5rem;
    }
    .stat-card {
        background: rgba(255,255,255,0.75);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid var(--border2);
        border-radius: var(--radius);
        padding: 1.2rem 1.4rem;
        position: relative;
        overflow: hidden;
        transition: border-color 0.25s, box-shadow 0.25s, transform 0.2s;
        box-shadow: 0 2px 12px rgba(139,92,246,0.06);
    }
    .stat-card:hover {
        border-color: var(--accent);
        box-shadow: 0 6px 24px rgba(139,92,246,0.14);
        transform: translateY(-2px);
    }
    .stat-card .accent-line {
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
    }
    .stat-card .stat-label {
        font-size: 0.7rem;
        font-family: 'DM Mono', monospace;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-bottom: 0.5rem;
    }
    .stat-card .stat-value {
        font-size: 2rem;
        font-weight: 800;
        line-height: 1;
        margin-bottom: 0.3rem;
    }
    .stat-card .stat-desc {
        font-size: 0.72rem;
        color: var(--muted);
    }

    /* 面板容器 */
    .panel {
        background: rgba(255,255,255,0.75);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid var(--border2);
        border-radius: var(--radius);
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 2px 16px rgba(139,92,246,0.05);
    }
    .panel-title {
        font-size: 0.7rem;
        font-family: 'DM Mono', monospace;
        background: var(--grad-main);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-transform: uppercase;
        letter-spacing: 0.1em;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .panel-title::before {
        content: '';
        display: inline-block;
        width: 6px; height: 6px;
        background: var(--grad-main);
        border-radius: 50%;
        flex-shrink: 0;
    }

    /* 結果表格 */
    .result-row {
        display: grid;
        grid-template-columns: 50px 1fr 140px 160px auto;
        gap: 12px;
        align-items: center;
        padding: 0.9rem 1rem;
        border-bottom: 1px solid var(--border);
        transition: background 0.15s;
    }
    .result-row:hover { background: rgba(139,92,246,0.04); }
    .result-row:last-child { border-bottom: none; }
    .type-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 0.68rem;
        font-family: 'DM Mono', monospace;
        font-weight: 500;
    }
    .badge-product {
        background: rgba(0,229,255,0.12);
        color: var(--accent);
        border: 1px solid rgba(0,229,255,0.25);
    }
    .badge-video {
        background: rgba(124,58,237,0.15);
        color: #a78bfa;
        border: 1px solid rgba(124,58,237,0.3);
    }
    .badge-unknown {
        background: rgba(100,116,139,0.15);
        color: var(--muted);
        border: 1px solid rgba(100,116,139,0.3);
    }
    .tag-chip {
        display: inline-block;
        background: linear-gradient(90deg, rgba(139,92,246,0.08), rgba(236,72,153,0.06));
        border: 1px solid rgba(139,92,246,0.18);
        color: var(--accent);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.65rem;
        font-family: 'DM Mono', monospace;
        margin: 2px;
    }
    .item-name {
        font-size: 0.875rem;
        font-weight: 600;
        color: var(--text);
        margin-bottom: 4px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .item-url {
        font-size: 0.68rem;
        font-family: 'DM Mono', monospace;
        color: var(--muted);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    .platform-name {
        font-size: 0.75rem;
        color: var(--muted);
        font-family: 'DM Mono', monospace;
    }
    .time-ms {
        font-size: 0.7rem;
        font-family: 'DM Mono', monospace;
        color: var(--muted);
        text-align: right;
    }
    .status-ok  { color: var(--success); }
    .status-err { color: var(--danger); }

    /* 進度條 */
    .progress-bar-wrap {
        background: var(--border);
        border-radius: 4px;
        height: 6px;
        margin-top: 6px;
        overflow: hidden;
    }
    .progress-bar-fill {
        height: 100%;
        border-radius: 4px;
        background: linear-gradient(90deg, var(--accent), var(--accent2));
        transition: width 0.3s ease;
    }

    /* Streamlit 元件覆寫 */
    .stTextArea textarea, .stTextInput input {
        background: rgba(255,255,255,0.85) !important;
        border: 1px solid var(--border2) !important;
        color: var(--text) !important;
        font-family: 'DM Mono', monospace !important;
        font-size: 0.85rem !important;
        border-radius: 8px !important;
        box-shadow: inset 0 1px 4px rgba(139,92,246,0.05) !important;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px rgba(139,92,246,0.12) !important;
    }
    .stSlider [data-baseweb="slider"] { padding: 0 !important; }
    /* 主要按鈕：紫→粉 漸層 */
    .stButton > button {
        background: var(--grad-main) !important;
        color: #ffffff !important;
        font-family: 'Syne', sans-serif !important;
        font-weight: 700 !important;
        font-size: 0.875rem !important;
        border: none !important;
        border-radius: 10px !important;
        padding: 0.6rem 1.5rem !important;
        letter-spacing: 0.02em !important;
        box-shadow: 0 4px 14px rgba(139,92,246,0.25) !important;
        transition: opacity 0.2s, transform 0.15s, box-shadow 0.2s !important;
    }
    .stButton > button:hover {
        opacity: 0.92 !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(139,92,246,0.35) !important;
    }
    /* 下載按鈕：柔和紫邊框 */
    .stDownloadButton > button {
        background: rgba(139,92,246,0.08) !important;
        color: var(--accent) !important;
        border: 1px solid rgba(139,92,246,0.28) !important;
        font-family: 'Syne', sans-serif !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        transition: background 0.2s, box-shadow 0.2s !important;
    }
    .stDownloadButton > button:hover {
        background: rgba(139,92,246,0.14) !important;
        box-shadow: 0 4px 12px rgba(139,92,246,0.15) !important;
    }
    div[data-testid="stExpander"] {
        background: rgba(255,255,255,0.70) !important;
        border: 1px solid var(--border2) !important;
        border-radius: var(--radius) !important;
        backdrop-filter: blur(8px) !important;
    }
    .stCheckbox label, .stRadio label { color: var(--text) !important; }
    label[data-testid="stWidgetLabel"] { color: var(--muted) !important; font-size: 0.78rem !important; }

    /* ── Sidebar 分區標題 ── */
    .sb-section {
        margin: 1.2rem 0 0.6rem;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid var(--border2);
    }
    .sb-section-title {
        font-size: 0.62rem;
        font-family: 'DM Mono', monospace;
        background: var(--grad-main);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .sb-section-title::before {
        content: '';
        display: inline-block;
        width: 5px; height: 5px;
        background: var(--grad-main);
        border-radius: 50%;
        flex-shrink: 0;
    }

    /* ── Sidebar 資訊卡片 ── */
    .sb-info-card {
        background: rgba(255,255,255,0.60);
        border: 1px solid var(--border2);
        border-radius: 8px;
        padding: 10px 12px;
        margin-bottom: 8px;
    }
    .sb-info-label {
        font-size: 0.62rem;
        font-family: 'DM Mono', monospace;
        color: var(--muted);
        margin-bottom: 3px;
    }
    .sb-info-value {
        font-size: 1.1rem;
        font-weight: 700;
        font-family: 'Syne', sans-serif;
    }

    /* ── Sidebar 快速篩選按鈕 ── */
    .sb-filter-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px;
        margin-top: 6px;
    }
    .sb-filter-btn {
        background: rgba(255,255,255,0.65);
        border: 1px solid var(--border2);
        border-radius: 6px;
        padding: 6px 8px;
        font-size: 0.72rem;
        font-family: 'DM Mono', monospace;
        color: var(--muted);
        cursor: pointer;
        text-align: center;
        transition: border-color 0.15s, color 0.15s, background 0.15s;
    }
    .sb-filter-btn:hover  { border-color: var(--accent); color: var(--accent);
                            background: rgba(139,92,246,0.08); }
    .sb-filter-btn.active { border-color: var(--accent); color: var(--accent);
                            background: rgba(139,92,246,0.10); }

    /* ── Sidebar 歷史記錄項目 ── */
    .sb-history-item {
        background: rgba(255,255,255,0.60);
        border: 1px solid var(--border2);
        border-radius: 6px;
        padding: 8px 10px;
        margin-bottom: 5px;
        cursor: pointer;
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    .sb-history-item:hover {
        border-color: var(--accent);
        box-shadow: 0 2px 10px rgba(139,92,246,0.10);
    }
    .sb-history-time {
        font-size: 0.6rem;
        font-family: 'DM Mono', monospace;
        color: var(--muted);
        margin-bottom: 2px;
    }
    .sb-history-meta {
        font-size: 0.72rem;
        color: var(--text);
    }

    /* ── Sidebar compliance 區塊 ── */
    .sb-compliance {
        background: linear-gradient(135deg,
            rgba(5,150,105,0.07) 0%,
            rgba(139,92,246,0.06) 100%);
        border: 1px solid rgba(5,150,105,0.20);
        border-radius: 8px;
        padding: 10px 12px;
        margin-top: 8px;
    }
    .sb-compliance-title {
        font-size: 0.62rem;
        font-family: 'DM Mono', monospace;
        color: var(--success);
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 5px;
    }
    .sb-compliance-item {
        font-size: 0.68rem;
        color: var(--muted);
        line-height: 1.8;
        font-family: 'DM Mono', monospace;
    }

    /* ── Sidebar slider 數值顯示優化 ── */
    [data-testid="stSidebar"] .stSlider {
        padding-bottom: 0.2rem;
    }
    [data-testid="stSidebar"] label {
        font-size: 0.72rem !important;
        color: var(--muted) !important;
        font-family: 'DM Mono', monospace !important;
    }
    [data-testid="stSidebar"] .stCheckbox label {
        font-size: 0.78rem !important;
        color: var(--text) !important;
        font-family: 'Syne', sans-serif !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] {
        background: rgba(255,255,255,0.80) !important;
        border-color: var(--border2) !important;
        border-radius: 8px !important;
    }
    [data-testid="stSidebar"] [data-baseweb="select"] * {
        background: rgba(255,255,255,0.90) !important;
        color: var(--text) !important;
        font-family: 'DM Mono', monospace !important;
        font-size: 0.78rem !important;
    }

    /* ── Sidebar 分隔線 ── */
    [data-testid="stSidebar"] hr {
        border-color: var(--border) !important;
        margin: 0.8rem 0 !important;
    }

    /* ── 隱藏 Streamlit sidebar nav 預設樣式 ── */
    [data-testid="stSidebarNav"] { display: none; }
    </style>
    """,
        unsafe_allow_html=True,
    )


def _render_hero() -> None:
    st.markdown(
        """
    <div class="hero-header">
        <p class="hero-title">🕸 Web Crawler</p>
        <p class="hero-sub">資料搜集與彙整分析 · 電商商品 / 影片內容</p>
        <span class="compliance-badge">
            ✓ 合規模式 · 僅供內部分析 · 不進行商業使用及二次上傳
        </span>
    </div>
    """,
        unsafe_allow_html=True,
    )


def _render_stat_cards(results: list[CollectedItem]) -> None:
    total = len(results)
    success = sum(1 for r in results if not r.error)
    products = sum(1 for r in results if r.content_type == ContentType.PRODUCT)
    videos = sum(1 for r in results if r.content_type == ContentType.VIDEO)
    avg_ms = int(sum(r.fetch_time_ms for r in results) / total) if total else 0
    all_tags = sum(len(r.tags) for r in results)

    st.markdown(
        f"""
    <div class="stat-grid">
        <div class="stat-card">
            <div class="accent-line" style="background:linear-gradient(90deg,#8b5cf6,#a78bfa)"></div>
            <div class="stat-label">總計爬取</div>
            <div class="stat-value" style="color:#8b5cf6">{total}</div>
            <div class="stat-desc">筆資料</div>
        </div>
        <div class="stat-card">
            <div class="accent-line" style="background:linear-gradient(90deg,#059669,#34d399)"></div>
            <div class="stat-label">成功率</div>
            <div class="stat-value" style="color:#059669">{int(success/total*100) if total else 0}%</div>
            <div class="stat-desc">{success} / {total} 成功</div>
        </div>
        <div class="stat-card">
            <div class="accent-line" style="background:linear-gradient(90deg,#8b5cf6,#ec4899)"></div>
            <div class="stat-label">內容分佈</div>
            <div class="stat-value" style="color:#8b5cf6">{products}<span style="font-size:1rem;color:#64748b"> / </span>{videos}</div>
            <div class="stat-desc">商品 / 影片</div>
        </div>
        <div class="stat-card">
            <div class="accent-line" style="background:linear-gradient(90deg,#ec4899,#f9a8d4)"></div>
            <div class="stat-label">收集標籤</div>
            <div class="stat-value" style="color:#ec4899">{all_tags}</div>
            <div class="stat-desc">平均 {avg_ms} ms/頁</div>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def _render_results_table(results: list[CollectedItem]) -> None:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown('<div class="panel-title">爬取結果</div>', unsafe_allow_html=True)

    # 篩選列
    col_filter, col_search = st.columns([2, 3])
    with col_filter:
        sb_default = st.session_state.get("sb_filter", "全部")
        filter_options = ["全部", "商品", "影片", "未知", "失敗"]
        sb_idx = filter_options.index(sb_default) if sb_default in filter_options else 0
        filter_type = st.selectbox(
            "篩選類型",
            filter_options,
            index=sb_idx,
            label_visibility="collapsed",
        )
    with col_search:
        search_kw = st.text_input(
            "搜尋",
            placeholder="🔍  搜尋名稱或標籤...",
            label_visibility="collapsed",
        )

    # 套用篩選
    filtered = results
    if filter_type == "商品":
        filtered = [r for r in filtered if r.content_type == ContentType.PRODUCT]
    elif filter_type == "影片":
        filtered = [r for r in filtered if r.content_type == ContentType.VIDEO]
    elif filter_type == "未知":
        filtered = [r for r in filtered if r.content_type == ContentType.UNKNOWN]
    elif filter_type == "失敗":
        filtered = [r for r in filtered if r.error]
    if search_kw:
        kw = search_kw.lower()
        filtered = [
            r
            for r in filtered
            if kw in r.name.lower() or any(kw in t.lower() for t in r.tags)
        ]

    st.markdown(
        f"<p style='font-size:0.75rem;color:#64748b;margin:0.5rem 0 1rem'>顯示 {len(filtered)} / {len(results)} 筆</p>",
        unsafe_allow_html=True,
    )

    for item in filtered:
        # 類型標籤
        if item.content_type == ContentType.PRODUCT:
            badge = '<span class="type-badge badge-product">商品</span>'
        elif item.content_type == ContentType.VIDEO:
            badge = '<span class="type-badge badge-video">影片</span>'
        else:
            badge = '<span class="type-badge badge-unknown">未知</span>'

        # 標籤 chips（最多5個）
        tag_html = "".join(f'<span class="tag-chip">{t}</span>' for t in item.tags[:5])
        if len(item.tags) > 5:
            tag_html += f'<span class="tag-chip">+{len(item.tags)-5}</span>'

        status_cls = "status-err" if item.error else "status-ok"
        status_icon = "✗" if item.error else "✓"

        st.markdown(
            f"""
        <div class="result-row">
            <div>{badge}</div>
            <div>
                <div class="item-name" title="{item.name}">{item.name[:60]}{'…' if len(item.name)>60 else ''}</div>
                <div class="item-url" title="{item.url}">{item.url[:70]}{'…' if len(item.url)>70 else ''}</div>
                <div style="margin-top:4px">{tag_html}</div>
            </div>
            <div class="platform-name">{item.source_platform or '—'}</div>
            <div>
                {'<span style="color:#ef4444;font-size:0.72rem;font-family:DM Mono">'+item.error+'</span>' if item.error else tag_html and ''}
            </div>
            <div class="time-ms">
                <span class="{status_cls}">{status_icon}</span>
                <br>{item.fetch_time_ms} ms
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)


def _to_dataframe(results: list[CollectedItem]) -> pd.DataFrame:
    rows = []
    for item in results:
        rows.append(
            {
                "類型": item.content_type.value,
                "名稱": item.name,
                "連結": item.url,
                "標籤": "、".join(item.tags),
                "平台": item.source_platform,
                "縮圖連結": item.thumbnail_url or "",
                "耗時(ms)": item.fetch_time_ms,
                "狀態": "失敗: " + item.error if item.error else "成功",
            }
        )
    return pd.DataFrame(rows)


# ════════════════════════════════════════════════════════
#  主頁面入口
# ════════════════════════════════════════════════════════


def show() -> None:
    st.set_page_config(
        page_title="Web Crawler · StProject",
        page_icon="🕸",
        layout="wide",
    )
    _inject_styles()
    _render_hero()

    # ── Session state 初始化 ────────────────────────────────
    if "crawl_history" not in st.session_state:
        st.session_state["crawl_history"] = []  # list of dict
    if "sb_filter" not in st.session_state:
        st.session_state["sb_filter"] = "全部"

    # ── Sidebar ──────────────────────────────────────────
    with st.sidebar:

        # ▌ Logo / 標題
        st.markdown(
            """
        <div style='padding:1rem 0 0.5rem;border-bottom:1px solid rgba(148,130,210,0.22);margin-bottom:0.5rem'>
            <div style='font-size:1.1rem;font-weight:800;font-family:Syne,sans-serif;
                        background:linear-gradient(90deg,#8b5cf6,#ec4899);
                        -webkit-background-clip:text;-webkit-text-fill-color:transparent'>
                🕸 Crawler
            </div>
            <div style='font-size:0.62rem;color:#7c6fa0;font-family:DM Mono,monospace;margin-top:2px'>
                StProject · v1.0
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # ════════════════════════════════
        # 區塊 1：爬蟲參數
        # ════════════════════════════════
        st.markdown(
            '<div class="sb-section"><div class="sb-section-title">爬蟲參數</div></div>',
            unsafe_allow_html=True,
        )

        concurrency = st.slider(
            "⚡ 並發數",
            min_value=1,
            max_value=8,
            value=3,
            help="同時爬取的連結數，建議 ≤ 5",
        )
        delay = st.slider(
            "⏱ 請求間隔（秒）",
            min_value=0.5,
            max_value=5.0,
            value=1.5,
            step=0.5,
            help="每次請求的等待時間，值越高對目標越友善",
        )
        timeout = st.slider(
            "⌛ 逾時上限（秒）",
            min_value=5,
            max_value=30,
            value=15,
            help="單頁最長等待時間",
        )
        max_urls = st.slider(
            "📋 單批上限",
            min_value=5,
            max_value=50,
            value=20,
            step=5,
            help="單次爬取的 URL 數量上限",
        )

        # ════════════════════════════════
        # 區塊 2：內容設定
        # ════════════════════════════════
        st.markdown(
            '<div class="sb-section"><div class="sb-section-title">內容設定</div></div>',
            unsafe_allow_html=True,
        )

        content_mode = st.selectbox(
            "🎯 內容類型",
            ["自動偵測", "僅商品", "僅影片"],
            help="強制指定解析模式，或讓系統自動判斷",
        )
        max_tags = st.slider(
            "🏷 標籤數量上限",
            min_value=3,
            max_value=20,
            value=10,
            help="每筆結果保留的標籤數量",
        )
        include_thumbnail = st.checkbox(
            "縮圖連結", value=True, help="是否擷取 og:image 縮圖 URL"
        )

        # ════════════════════════════════
        # 區塊 3：合規控制
        # ════════════════════════════════
        st.markdown(
            '<div class="sb-section"><div class="sb-section-title">合規控制</div></div>',
            unsafe_allow_html=True,
        )

        respect_robots = st.checkbox(
            "遵守 robots.txt", value=True, help="建議保持開啟，自動跳過禁止爬取的頁面"
        )
        enable_dedup = st.checkbox(
            "URL 去重複", value=True, help="自動移除重複的輸入 URL"
        )
        strip_personal = st.checkbox(
            "個資自動過濾", value=True, help="自動遮蔽結果中的電話、Email 等個人資料"
        )

        st.markdown(
            """
        <div class="sb-compliance">
            <div class="sb-compliance-title">✓ 使用聲明</div>
            <div class="sb-compliance-item">
                · 僅供內部資料分析<br>
                · 不進行商業使用<br>
                · 不進行二次上傳<br>
                · 遵守目標網站 ToS
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # ════════════════════════════════
        # 區塊 4：結果快篩（有結果時才顯示）
        # ════════════════════════════════
        if "crawl_results" in st.session_state:
            results_snapshot = st.session_state["crawl_results"]
            n_total = len(results_snapshot)
            n_product = sum(
                1 for r in results_snapshot if r.content_type == ContentType.PRODUCT
            )
            n_video = sum(
                1 for r in results_snapshot if r.content_type == ContentType.VIDEO
            )
            n_fail = sum(1 for r in results_snapshot if r.error)

            st.markdown(
                '<div class="sb-section"><div class="sb-section-title">結果快篩</div></div>',
                unsafe_allow_html=True,
            )

            st.markdown(
                f"""
            <div class="sb-filter-grid">
                <div class="sb-filter-btn">全部 ({n_total})</div>
                <div class="sb-filter-btn">商品 ({n_product})</div>
                <div class="sb-filter-btn">影片 ({n_video})</div>
                <div class="sb-filter-btn" style="color:#ef4444;border-color:rgba(239,68,68,0.3)">
                    失敗 ({n_fail})
                </div>
            </div>
            """,
                unsafe_allow_html=True,
            )

            sb_filter = st.radio(
                "快篩",
                ["全部", "商品", "影片", "未知", "失敗"],
                horizontal=False,
                label_visibility="collapsed",
                key="sb_filter_radio",
            )
            st.session_state["sb_filter"] = sb_filter

        # ════════════════════════════════
        # 區塊 5：爬取歷史
        # ════════════════════════════════
        history = st.session_state.get("crawl_history", [])
        if history:
            st.markdown(
                '<div class="sb-section"><div class="sb-section-title">爬取歷史</div></div>',
                unsafe_allow_html=True,
            )
            for i, rec in enumerate(reversed(history[-5:])):
                st.markdown(
                    f"""
                <div class="sb-history-item">
                    <div class="sb-history-time">{rec['time']}</div>
                    <div class="sb-history-meta">
                        {rec['count']} 筆 · {rec['success']} 成功
                        <span style='float:right;font-size:0.65rem;color:#475569'>{rec['elapsed']}s</span>
                    </div>
                </div>
                """,
                    unsafe_allow_html=True,
                )
            if st.button("🗑  清除歷史", use_container_width=True):
                st.session_state["crawl_history"] = []
                st.rerun()

    # ── 主內容區 ──────────────────────────────────────────
    col_input, col_preview = st.columns([3, 2], gap="large")

    with col_input:
        st.markdown(
            '<div class="panel-title">目標 URL 輸入</div>', unsafe_allow_html=True
        )
        url_input = st.text_area(
            "URLs",
            height=200,
            placeholder="每行輸入一個 URL，例如：\nhttps://shopee.tw/product/xxx\nhttps://www.youtube.com/watch?v=xxx",
            label_visibility="collapsed",
        )

        col_btn, col_clear = st.columns([2, 1])
        with col_btn:
            start_btn = st.button("🚀  開始爬取", use_container_width=True)
        with col_clear:
            if st.button("清除結果", use_container_width=True):
                for key in ["crawl_results", "crawl_df"]:
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

    with col_preview:
        st.markdown('<div class="panel-title">支援平台</div>', unsafe_allow_html=True)
        st.markdown(
            """
        <div style='display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:0.5rem'>
            <div style='background:rgba(139,92,246,0.07);border:1px solid rgba(139,92,246,0.18);border-radius:8px;padding:10px 14px'>
                <div style='font-size:0.65rem;background:linear-gradient(90deg,#8b5cf6,#ec4899);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-family:DM Mono,monospace;margin-bottom:4px'>PRODUCT</div>
                <div style='font-size:0.8rem;color:#1e1b4b'>🛒 蝦皮 / PChome</div>
                <div style='font-size:0.8rem;color:#1e1b4b'>🛍 momo / 博客來</div>
                <div style='font-size:0.8rem;color:#1e1b4b'>📦 Amazon</div>
            </div>
            <div style='background:rgba(236,72,153,0.07);border:1px solid rgba(236,72,153,0.18);border-radius:8px;padding:10px 14px'>
                <div style='font-size:0.65rem;background:linear-gradient(90deg,#ec4899,#8b5cf6);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-family:DM Mono,monospace;margin-bottom:4px'>VIDEO</div>
                <div style='font-size:0.8rem;color:#1e1b4b'>▶ YouTube</div>
                <div style='font-size:0.8rem;color:#1e1b4b'>📺 Bilibili</div>
                <div style='font-size:0.8rem;color:#1e1b4b'>🎮 Twitch / Vimeo</div>
            </div>
        </div>
        <div style='margin-top:8px;background:rgba(255,255,255,0.60);border:1px solid rgba(148,130,210,0.18);border-radius:8px;padding:10px 14px'>
            <div style='font-size:0.65rem;color:#7c6fa0;font-family:DM Mono,monospace;margin-bottom:4px'>AUTO-DETECT</div>
            <div style='font-size:0.8rem;color:#4c1d95'>其他網站自動偵測 og:title / keywords</div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # ── 執行爬取 ──────────────────────────────────────────
    if start_btn:
        raw_urls = [u.strip() for u in url_input.splitlines() if u.strip()]

        # URL 去重複（由 sidebar 控制）
        urls = list(dict.fromkeys(raw_urls)) if enable_dedup else raw_urls
        dedup_removed = len(raw_urls) - len(urls)
        if dedup_removed > 0:
            st.info(f"🔍 已移除 {dedup_removed} 個重複 URL")

        if not urls:
            st.warning("請輸入至少一個 URL。")
        elif len(urls) > max_urls:
            st.error(f"超過單批上限 {max_urls} 個 URL，請減少輸入或在側邊欄調整上限。")
        else:
            config = CrawlerConfig(
                max_concurrency=concurrency,
                request_delay=delay,
                timeout=float(timeout),
                respect_robots=respect_robots,
            )

            progress_bar = st.progress(0)
            status_text = st.empty()
            status_text.markdown(
                f'<p style="font-size:0.8rem;color:#64748b;font-family:DM Mono,monospace">正在爬取 {len(urls)} 個頁面...</p>',
                unsafe_allow_html=True,
            )

            with st.spinner(""):
                start_time = time.monotonic()
                results = run_crawl(urls, config)
                elapsed = time.monotonic() - start_time

            # ── 套用 content_mode 強制覆蓋類型 ──
            if content_mode == "僅商品":
                for r in results:
                    if not r.error:
                        r.content_type = ContentType.PRODUCT
            elif content_mode == "僅影片":
                for r in results:
                    if not r.error:
                        r.content_type = ContentType.VIDEO

            # ── 截斷標籤數量 ──
            for r in results:
                r.tags = r.tags[:max_tags]

            # ── 移除縮圖（若未勾選）──
            if not include_thumbnail:
                for r in results:
                    r.thumbnail_url = None

            # ── 個資過濾 ──
            if strip_personal:
                import re as _re

                _phone = _re.compile(r"09\d{2}[\-\s]?\d{3}[\-\s]?\d{3}")
                _email = _re.compile(r"[\w.+\-]+@[\w\-]+\.[a-zA-Z]{2,}")
                _id = _re.compile(r"[A-Z][12]\d{8}")
                for r in results:
                    r.name = _phone.sub(
                        "[電話]", _email.sub("[Email]", _id.sub("[ID]", r.name))
                    )
                    r.tags = [
                        _phone.sub("[電話]", _email.sub("[Email]", t)) for t in r.tags
                    ]

            progress_bar.progress(1.0)
            status_text.markdown(
                f'<p style="font-size:0.8rem;color:#10b981;font-family:DM Mono,monospace">✓ 完成，耗時 {elapsed:.1f} 秒</p>',
                unsafe_allow_html=True,
            )

            st.session_state["crawl_results"] = results
            st.session_state["crawl_df"] = _to_dataframe(results)

            # ── 寫入歷史記錄 ──
            import datetime as _dt

            st.session_state["crawl_history"].append(
                {
                    "time": _dt.datetime.now().strftime("%m/%d %H:%M"),
                    "count": len(results),
                    "success": sum(1 for r in results if not r.error),
                    "elapsed": f"{elapsed:.1f}",
                }
            )

    # ── 結果展示 ──────────────────────────────────────────
    if "crawl_results" in st.session_state:
        results: list[CollectedItem] = st.session_state["crawl_results"]
        df: pd.DataFrame = st.session_state["crawl_df"]

        st.markdown("---")
        _render_stat_cards(results)
        _render_results_table(results)

        # 下載區
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.markdown('<div class="panel-title">匯出資料</div>', unsafe_allow_html=True)
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="📥  下載 CSV",
                data=df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"crawl_results_{int(time.time())}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with dl_col2:
            st.download_button(
                label="📥  下載 JSON",
                data=df.to_json(orient="records", force_ascii=False, indent=2).encode(
                    "utf-8"
                ),
                file_name=f"crawl_results_{int(time.time())}.json",
                mime="application/json",
                use_container_width=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

        # 展開原始表格
        with st.expander("📊 查看完整資料表"):
            st.dataframe(df, use_container_width=True, height=400)


# 直接執行時使用
if __name__ == "__main__":
    show()
