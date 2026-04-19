"""
網頁爬蟲功能頁面 - crawler_dashboard.py
放置路徑：pages/crawler_dashboard.py
用途：資料搜集與彙整分析（商品名稱/連結/影片名稱/標籤）
限制：僅供內部分析，不進行商業使用及二次上傳
"""

from __future__ import annotations

import asyncio
import json
import re
import subprocess
import sys
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable
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
#  Playwright 瀏覽器渲染核心
# ════════════════════════════════════════════════════════


def fetch_with_browser_sync(
    url: str,
    wait_selector: str = "body",
    timeout_ms: int = 20000,
    scroll_to_bottom: bool = False,
) -> tuple[str, str]:
    """
    透過獨立子程序執行 Playwright，完全迴避 Windows event loop 衝突。
    回傳 (html, final_url)。
    """
    from pathlib import Path

    # 找到 playwright_runner.py 的絕對路徑
    runner_path = Path(__file__).parent.parent / "playwright_runner.py"
    if not runner_path.exists():
        raise FileNotFoundError(
            f"找不到 playwright_runner.py，請確認放在專案根目錄：{runner_path}"
        )

    payload = json.dumps(
        {
            "url": url,
            "wait_selector": wait_selector,
            "timeout_ms": timeout_ms,
            "scroll_to_bottom": scroll_to_bottom,
        },
        ensure_ascii=False,
    )

    result = subprocess.run(
        [sys.executable, str(runner_path)],
        input=payload.encode("utf-8"),
        capture_output=True,
        timeout=timeout_ms / 1000 + 10,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"playwright_runner 執行失敗：\n{result.stderr.decode('utf-8', errors='replace')}"
        )

    output = json.loads(result.stdout.decode("utf-8"))

    if output.get("error"):
        raise RuntimeError(f"Playwright 錯誤：{output['error']}")

    return output["html"], output["final_url"]


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
    last_error = ""

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
        error=f"失敗（重試 {config.max_retries} 次）：{last_error}",
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
        for coro in asyncio.as_completed(tasks):
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
#  自訂 Tag 擷取
# ════════════════════════════════════════════════════════


@dataclass
class TagExtractResult:
    """單一 selector 的擷取結果"""

    selector: str
    attribute: str
    matched_count: int
    contents: list[str]       # 每個節點的文字內容
    html_snippets: list[str]  # 每個節點的 outer HTML（供預覽）
    error: Optional[str] = None


@dataclass
class CustomTagCrawlResult:
    """單一 URL + 多個 selector 的完整結果"""

    url: str
    fetch_time_ms: int
    tag_results: list[TagExtractResult]
    error: Optional[str] = None


def extract_tags_from_tree(
    tree: HTMLParser,
    queries: list[tuple[str, str]],
    max_nodes_per_selector: int = 20,
    text_max_len: int = 500,
    base_url: str = "",
) -> list[TagExtractResult]:
    """
    從已解析的 HTMLParser 中，依序擷取每個 CSS selector 對應的內容。

    Args:
        queries:    [(selector, attribute), ...]
                    attribute 為空字串時取節點文字內容
                    attribute 為 "href"/"src" 等時取對應屬性值
        base_url:   用來補全相對路徑

    Returns:
        每個 selector 對應的 TagExtractResult 列表
    """
    results: list[TagExtractResult] = []

    for selector, attribute in queries:
        selector = selector.strip()
        attribute = attribute.strip()
        if not selector:
            continue
        try:
            nodes = tree.css(selector)[:max_nodes_per_selector]
            contents: list[str] = []
            html_snippets: list[str] = []

            for node in nodes:
                if attribute:
                    # 取指定屬性值
                    value = node.attributes.get(attribute, "")
                    # href / src 補全相對路徑
                    if (
                        attribute in ("href", "src")
                        and value
                        and not value.startswith("http")
                        and base_url
                    ):
                        value = urljoin(base_url, value)
                    display = value
                else:
                    # 無指定屬性，取文字內容
                    display = node.text(strip=True, separator=" ")

                if display:
                    contents.append(display[:text_max_len])
                html_snippets.append((node.html or "")[:300])

            results.append(
                TagExtractResult(
                    selector=selector,
                    attribute=attribute or "（文字內容）",
                    matched_count=len(nodes),
                    contents=contents,
                    html_snippets=html_snippets,
                )
            )

        except Exception as e:
            results.append(
                TagExtractResult(
                    selector=selector,
                    attribute=attribute,
                    matched_count=0,
                    contents=[],
                    html_snippets=[],
                    error=f"Selector 錯誤：{e}",
                )
            )

    return results


async def fetch_and_extract_tags(
    url: str,
    queries: list[tuple[str, str]],
    config: CrawlerConfig,
    max_nodes: int = 20,
    use_browser: bool = False,
    scroll_to_bottom: bool = False,
) -> CustomTagCrawlResult:
    """
    爬取單一 URL 並依照自訂 selector 擷取內容。
    複用 CrawlerConfig 的 headers / timeout / retry 設定。
    """
    start = time.monotonic()

    # 安全驗證
    try:
        CollectedItem(url=url, name="_validate_only")
    except Exception as e:
        return CustomTagCrawlResult(
            url=url,
            fetch_time_ms=0,
            tag_results=[],
            error=f"URL 安全驗證失敗：{e}",
        )

    try:
        if use_browser:
            wait_sel = queries[0][0] if queries else "body"
            html, final_url = fetch_with_browser_sync(
                url,
                wait_selector=wait_sel,
                timeout_ms=int(config.timeout * 1000),
                scroll_to_bottom=scroll_to_bottom,
            )
        else:
            async with httpx.AsyncClient(
                headers=config.headers,
                timeout=config.timeout,
                http2=True,
                follow_redirects=True,
            ) as client:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                html = resp.text
                final_url = str(resp.url)

        tree = HTMLParser(html)
        for noise in tree.css("script, style, noscript"):
            noise.decompose()

        tag_results = extract_tags_from_tree(
            tree, queries, max_nodes, base_url=final_url
        )

        return CustomTagCrawlResult(
            url=url,
            fetch_time_ms=int((time.monotonic() - start) * 1000),
            tag_results=tag_results,
        )

    except Exception as e:
        return CustomTagCrawlResult(
            url=url,
            fetch_time_ms=int((time.monotonic() - start) * 1000),
            tag_results=[],
            error=str(e),
        )


def run_tag_extract(
    url: str,
    queries: list[tuple[str, str]],
    config: CrawlerConfig,
    max_nodes: int = 20,
    use_browser: bool = False,
    scroll_to_bottom: bool = False,
) -> CustomTagCrawlResult:
    """Streamlit 同步包裝器"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            fetch_and_extract_tags(
                url,
                queries,
                config,
                max_nodes,
                use_browser=use_browser,
                scroll_to_bottom=scroll_to_bottom,
            )
        )
    finally:
        loop.close()


# ════════════════════════════════════════════════════════
#  二階段爬蟲工作流 (Two-Stage Pipeline)
#  Stage 1：從列表頁擷取 href 連結
#  Stage 2：逐一深度爬取各詳情頁內容
# ════════════════════════════════════════════════════════


@dataclass
class StageConfig:
    """
    單一爬蟲階段的設定。
    每個 Stage 可獨立設定 selector、目標屬性與解析策略。
    """
    selectors: list[tuple[str, str]]   # [(selector, attribute), ...]
    label: str = "Stage"
    use_browser: bool = False
    scroll_to_bottom: bool = False
    max_nodes: int = 20


@dataclass
class PipelineStageResult:
    """單一 Stage 對單一 URL 的執行結果。"""
    source_url: str
    stage_label: str
    tag_results: list[TagExtractResult]
    fetch_time_ms: int = 0
    error: Optional[str] = None


@dataclass
class TwoStagePipelineResult:
    """
    完整兩階段工作流的結果。
    包含 Stage 1 的來源頁、抽出的連結、以及各詳情頁的 Stage 2 結果。
    """
    source_url: str
    extracted_links: list[str] = field(default_factory=list)
    stage2_results: list[PipelineStageResult] = field(default_factory=list)
    total_fetch_time_ms: int = 0
    error: Optional[str] = None


async def _run_pipeline_stage(
    url: str,
    stage_cfg: StageConfig,
    crawler_cfg: CrawlerConfig,
) -> PipelineStageResult:
    """執行單一階段的爬取與解析，內部複用 fetch_and_extract_tags。"""
    result = await fetch_and_extract_tags(
        url=url,
        queries=stage_cfg.selectors,
        config=crawler_cfg,
        max_nodes=stage_cfg.max_nodes,
        use_browser=stage_cfg.use_browser,
        scroll_to_bottom=stage_cfg.scroll_to_bottom,
    )
    return PipelineStageResult(
        source_url=url,
        stage_label=stage_cfg.label,
        tag_results=result.tag_results,
        fetch_time_ms=result.fetch_time_ms,
        error=result.error,
    )


def _extract_links_from_stage_result(
    result: PipelineStageResult,
    base_url: str,
    same_domain_only: bool = True,
    max_links: int = 50,
) -> list[str]:
    """
    從 Stage 1 結果中提取有效 href 連結。

    Args:
        result:           Stage 1 的 PipelineStageResult
        base_url:         列表頁的原始 URL（用於相對路徑補全）
        same_domain_only: 是否限制只爬同網域的連結（防止越域爬取）
        max_links:        最多提取幾條連結

    Returns:
        清理後的絕對 URL 列表
    """
    base_domain = urlparse(base_url).netloc
    links: list[str] = []
    seen: set[str] = set()

    for tag_result in result.tag_results:
        for raw_link in tag_result.contents:
            # 補全相對路徑
            full_url = urljoin(base_url, raw_link.strip())

            # 基本過濾
            parsed = urlparse(full_url)
            if parsed.scheme not in ("http", "https"):
                continue
            if same_domain_only and parsed.netloc != base_domain:
                continue
            if full_url in seen:
                continue

            seen.add(full_url)
            links.append(full_url)

            if len(links) >= max_links:
                break

        if len(links) >= max_links:
            break

    return links


async def run_two_stage_pipeline(
    source_url: str,
    stage1_cfg: StageConfig,
    stage2_cfg: StageConfig,
    crawler_cfg: CrawlerConfig,
    same_domain_only: bool = True,
    max_detail_pages: int = 20,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> TwoStagePipelineResult:
    """
    執行完整的兩階段爬蟲工作流。

    Stage 1：爬取列表頁，依 stage1_cfg.selectors 擷取所有目標 href
    Stage 2：對每個 href 執行深度爬取，依 stage2_cfg.selectors 解析詳情

    Args:
        source_url:        列表頁 URL（Stage 1 入口）
        stage1_cfg:        Stage 1 設定（selector 應指向 href 連結）
        stage2_cfg:        Stage 2 設定（selector 指向詳情頁的目標欄位）
        crawler_cfg:       共用爬蟲設定（速率、robots.txt 等）
        same_domain_only:  Stage 2 只爬取同網域連結（合規保護）
        max_detail_pages:  Stage 2 最多爬幾個詳情頁（防止無限爬取）
        progress_callback: 進度回呼 fn(current, total, current_url)
    """
    total_start = time.monotonic()

    # ── robots.txt 檢查（Stage 1 入口頁）──
    if crawler_cfg.respect_robots and not check_robots_allowed(source_url):
        return TwoStagePipelineResult(
            source_url=source_url,
            error=f"robots.txt 封鎖：{source_url}",
        )

    # ── Stage 1：爬取列表頁 ──
    stage1_result = await _run_pipeline_stage(source_url, stage1_cfg, crawler_cfg)

    if stage1_result.error:
        return TwoStagePipelineResult(
            source_url=source_url,
            error=f"Stage 1 失敗：{stage1_result.error}",
        )

    # ── 提取 href 連結 ──
    extracted_links = _extract_links_from_stage_result(
        result=stage1_result,
        base_url=source_url,
        same_domain_only=same_domain_only,
        max_links=max_detail_pages,
    )

    if not extracted_links:
        return TwoStagePipelineResult(
            source_url=source_url,
            extracted_links=[],
            error="Stage 1 未擷取到任何有效連結，請確認 Selector 是否正確",
        )

    # ── robots.txt 過濾（Stage 2 各詳情頁）──
    if crawler_cfg.respect_robots:
        filtered = [u for u in extracted_links if check_robots_allowed(u)]
        extracted_links = filtered

    if not extracted_links:
        return TwoStagePipelineResult(
            source_url=source_url,
            extracted_links=[],
            error="所有詳情頁連結皆被 robots.txt 封鎖",
        )

    # ── Stage 2：逐一爬取詳情頁（含速率控制）──
    semaphore = asyncio.Semaphore(crawler_cfg.max_concurrency)

    async def _fetch_detail(url: str, idx: int) -> PipelineStageResult:
        async with semaphore:
            if progress_callback:
                progress_callback(idx, len(extracted_links), url)
            result = await _run_pipeline_stage(url, stage2_cfg, crawler_cfg)
            # ⚠️ 尊重目標網站，每次請求後等待
            await asyncio.sleep(crawler_cfg.request_delay)
            return result

    tasks = [
        _fetch_detail(url, i) for i, url in enumerate(extracted_links, start=1)
    ]
    stage2_results: list[PipelineStageResult] = await asyncio.gather(
        *tasks, return_exceptions=False
    )

    total_ms = int((time.monotonic() - total_start) * 1000)

    return TwoStagePipelineResult(
        source_url=source_url,
        extracted_links=extracted_links,
        stage2_results=list(stage2_results),
        total_fetch_time_ms=total_ms,
    )


def run_two_stage_pipeline_sync(
    source_url: str,
    stage1_cfg: StageConfig,
    stage2_cfg: StageConfig,
    crawler_cfg: CrawlerConfig,
    same_domain_only: bool = True,
    max_detail_pages: int = 20,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> TwoStagePipelineResult:
    """Streamlit 同步包裝器，供 UI 層直接呼叫。"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(
            run_two_stage_pipeline(
                source_url=source_url,
                stage1_cfg=stage1_cfg,
                stage2_cfg=stage2_cfg,
                crawler_cfg=crawler_cfg,
                same_domain_only=same_domain_only,
                max_detail_pages=max_detail_pages,
                progress_callback=progress_callback,
            )
        )
    finally:
        loop.close()


def _pipeline_results_to_dataframe(
    pipeline_result: TwoStagePipelineResult,
) -> pd.DataFrame:
    """將 Pipeline 結果轉換為 DataFrame，方便匯出。"""
    rows = []
    for page_result in pipeline_result.stage2_results:
        # 將所有 selector 的結果攤平成 dict
        row: dict = {
            "來源列表頁": pipeline_result.source_url,
            "詳情頁 URL": page_result.source_url,
            "耗時(ms)": page_result.fetch_time_ms,
            "狀態": f"失敗: {page_result.error}" if page_result.error else "成功",
        }
        for tag_res in page_result.tag_results:
            col_name = f"{tag_res.selector}"
            if tag_res.attribute and tag_res.attribute != "（文字內容）":
                col_name += f"[{tag_res.attribute}]"
            row[col_name] = " | ".join(tag_res.contents[:5])
        rows.append(row)
    return pd.DataFrame(rows)


# ════════════════════════════════════════════════════════
#  Streamlit UI
# ════════════════════════════════════════════════════════


def _inject_styles() -> None:
    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@400;500&display=swap');

    :root {
        --bg:        #f0f4ff;
        --bg-end:    #faf5ff;
        --surface:   rgba(255,255,255,0.72);
        --surface2:  rgba(255,255,255,0.50);
        --border:    rgba(148,130,210,0.18);
        --border2:   rgba(168,148,228,0.28);
        --accent:    #8b5cf6;
        --accent2:   #ec4899;
        --accent-soft: rgba(139,92,246,0.12);
        --success:   #059669;
        --warn:      #d97706;
        --danger:    #dc2626;
        --text:      #1e1b4b;
        --text2:     #4c1d95;
        --muted:     #7c6fa0;
        --radius:    14px;
        --grad-main:  linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%);
        --grad-soft:  linear-gradient(135deg, rgba(139,92,246,0.15) 0%, rgba(236,72,153,0.10) 100%);
        --grad-bg:    linear-gradient(160deg, #f0f4ff 0%, #faf0ff 50%, #fff5f8 100%);
        --grad-sidebar: linear-gradient(180deg, #f5f0ff 0%, #fdf4ff 100%);
    }

    html, body, [data-testid="stAppViewContainer"] {
        background: var(--grad-bg) !important;
        background-attachment: fixed !important;
        color: var(--text) !important;
        font-family: 'Syne', sans-serif !important;
    }

    [data-testid="stSidebar"] {
        background: var(--grad-sidebar) !important;
        border-right: 1px solid var(--border2) !important;
    }
    [data-testid="stSidebar"] * { color: var(--text) !important; }
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
    [data-testid="stSidebar"] hr {
        border-color: var(--border) !important;
        margin: 0.8rem 0 !important;
    }
    [data-testid="stSidebarNav"] { display: none; }

    /* Hero Header */
    .hero-header {
        background: linear-gradient(135deg, #f5f0ff 0%, #fce7f3 100%);
        border: 1px solid var(--border2);
        border-radius: var(--radius);
        padding: 2rem 2.5rem;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
    }
    .hero-header::before {
        content: '';
        position: absolute;
        top: -60px; right: -60px;
        width: 200px; height: 200px;
        background: radial-gradient(circle, rgba(139,92,246,0.12) 0%, transparent 70%);
        border-radius: 50%;
    }
    .hero-title {
        font-size: 2rem;
        font-weight: 800;
        background: var(--grad-main);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0 0 0.3rem;
    }
    .hero-sub {
        font-size: 0.875rem;
        color: var(--muted);
        margin: 0 0 0.8rem;
    }
    .compliance-badge {
        display: inline-block;
        background: rgba(5,150,105,0.1);
        border: 1px solid rgba(5,150,105,0.25);
        color: var(--success);
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.7rem;
        font-family: 'DM Mono', monospace;
    }

    /* Stat Grid */
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

    /* Panel */
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

    /* Result Row */
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

    /* Streamlit overrides */
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

    /* Sidebar sections */
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
    .sb-compliance {
        background: rgba(5,150,105,0.06);
        border: 1px solid rgba(5,150,105,0.2);
        border-radius: 8px;
        padding: 10px 12px;
        margin-top: 0.8rem;
    }
    .sb-compliance-title {
        font-size: 0.65rem;
        font-family: 'DM Mono', monospace;
        color: var(--success);
        margin-bottom: 6px;
        font-weight: 600;
    }
    .sb-compliance-item {
        font-size: 0.72rem;
        color: #065f46;
        line-height: 1.6;
    }
    .sb-filter-grid {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 6px;
        margin-bottom: 0.6rem;
    }
    .sb-filter-btn {
        background: rgba(255,255,255,0.60);
        border: 1px solid var(--border2);
        border-radius: 6px;
        padding: 5px 8px;
        font-size: 0.68rem;
        font-family: 'DM Mono', monospace;
        color: var(--muted);
        text-align: center;
    }
    .sb-history-item {
        background: rgba(255,255,255,0.50);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 6px 10px;
        margin-bottom: 6px;
    }
    .sb-history-time {
        font-size: 0.62rem;
        font-family: 'DM Mono', monospace;
        color: var(--muted);
    }
    .sb-history-meta {
        font-size: 0.72rem;
        color: var(--text);
    }

    /* Pipeline specific */
    .pipeline-stage-header {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 14px;
        border-radius: 8px;
        margin-bottom: 12px;
        font-size: 0.8rem;
        font-weight: 700;
    }
    .stage1-header {
        background: rgba(59,130,246,0.08);
        border: 1px solid rgba(59,130,246,0.2);
        color: #1d4ed8;
    }
    .stage2-header {
        background: rgba(16,185,129,0.08);
        border: 1px solid rgba(16,185,129,0.2);
        color: #065f46;
    }
    .pipeline-link-item {
        font-size: 0.72rem;
        font-family: 'DM Mono', monospace;
        color: var(--accent);
        padding: 3px 0;
        border-bottom: 1px solid var(--border);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
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
    st.markdown('<div class="panel-title">爬取結果</div>', unsafe_allow_html=True)

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
        if item.content_type == ContentType.PRODUCT:
            badge = '<span class="type-badge badge-product">商品</span>'
        elif item.content_type == ContentType.VIDEO:
            badge = '<span class="type-badge badge-video">影片</span>'
        else:
            badge = '<span class="type-badge badge-unknown">未知</span>'

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
            <div>{'<span style="color:#ef4444;font-size:0.72rem;font-family:DM Mono">'+item.error+'</span>' if item.error else ''}</div>
            <div class="time-ms">
                <span class="{status_cls}">{status_icon}</span>
                <br>{item.fetch_time_ms} ms
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )


def _render_tag_extractor_panel() -> None:
    with st.container(border=True):
        st.markdown(
            '<div class="panel-title">🏷 自訂 Tag 擷取</div>',
            unsafe_allow_html=True,
        )

        target_url = st.text_input(
            "目標 URL",
            placeholder="https://example.com",
            key="tag_extract_url",
        )

        st.markdown(
            "<p style='font-size:0.8rem;color:#7c6fa0;margin:0.8rem 0 0.4rem'>"
            "查詢條件（可新增多列）</p>",
            unsafe_allow_html=True,
        )

        if "tag_queries" not in st.session_state:
            st.session_state["tag_queries"] = [{"selector": "", "attribute": ""}]

        queries = st.session_state["tag_queries"]

        for i, q in enumerate(queries):
            col_sel, col_attr, col_del = st.columns([4, 3, 1], vertical_alignment="bottom")
            with col_sel:
                queries[i]["selector"] = st.text_input(
                    f"CSS Selector #{i+1}",
                    value=q["selector"],
                    placeholder="例：div.goods-list a",
                    label_visibility="collapsed" if i > 0 else "visible",
                    key=f"selector_{i}",
                )
            with col_attr:
                queries[i]["attribute"] = st.text_input(
                    f"屬性 #{i+1}",
                    value=q["attribute"],
                    placeholder="屬性名稱，留空=取文字",
                    label_visibility="collapsed" if i > 0 else "visible",
                    key=f"attribute_{i}",
                )
            with col_del:
                if st.button("✕", key=f"del_{i}", disabled=len(queries) == 1):
                    queries.pop(i)
                    st.rerun()

        col_add, col_run = st.columns([1, 3])
        with col_add:
            if st.button("＋ 新增條件", width='stretch'):
                queries.append({"selector": "", "attribute": ""})
                st.rerun()
        with col_run:
            extract_btn = st.button(
                "🔍 開始擷取",
                type="primary",
                width='stretch',
                key="tag_extract_btn",
            )

        col_opt1, col_opt2 = st.columns(2)
        with col_opt1:
            max_nodes = st.number_input(
                "每個 Selector 最多節點數",
                min_value=1,
                max_value=50,
                value=10,
                key="tag_max_nodes",
            )
        with col_opt2:
            show_html = st.checkbox(
                "顯示原始 HTML 片段",
                value=False,
                key="tag_show_html",
            )

        col_browser, col_scroll = st.columns(2)
        with col_browser:
            use_browser = st.checkbox(
                "🌐 瀏覽器渲染模式",
                value=False,
                help="使用 Playwright 執行 JS，適用 momo、蝦皮等動態網站，速度較慢",
                key="tag_use_browser",
            )
        with col_scroll:
            scroll_to_bottom = st.checkbox(
                "📜 自動捲動到底部",
                value=False,
                help="捲動頁面觸發 lazy-load，商品列表頁建議開啟",
                key="tag_scroll_bottom",
                disabled=not use_browser,
            )

    if extract_btn:
        valid_queries = [
            (q["selector"], q["attribute"]) for q in queries if q["selector"].strip()
        ]
        if not target_url:
            st.warning("請輸入目標 URL。")
        elif not valid_queries:
            st.warning("請輸入至少一個 CSS Selector。")
        else:
            config = CrawlerConfig(max_concurrency=1, request_delay=1.0, timeout=15.0)
            with st.spinner("擷取中..."):
                result = run_tag_extract(
                    target_url,
                    valid_queries,
                    config,
                    max_nodes,
                    use_browser=use_browser,
                    scroll_to_bottom=scroll_to_bottom,
                )
            st.session_state["tag_extract_result"] = result

    if "tag_extract_result" in st.session_state:
        result: CustomTagCrawlResult = st.session_state["tag_extract_result"]

        with st.container(border=True):
            if result.error:
                st.error(f"❌ 爬取失敗：{result.error}")
            else:
                st.markdown(
                    f"<p style='font-size:0.75rem;color:#64748b'>"
                    f"✓ 耗時 {result.fetch_time_ms} ms · "
                    f"{len(result.tag_results)} 個條件</p>",
                    unsafe_allow_html=True,
                )
                for tag_result in result.tag_results:
                    label = f"`{tag_result.selector}`"
                    if tag_result.attribute:
                        label += f" → `{tag_result.attribute}`"
                    label += f"  （{tag_result.matched_count} 個節點）"

                    with st.expander(label, expanded=True):
                        if tag_result.error:
                            st.error(tag_result.error)
                            continue
                        if not tag_result.contents:
                            st.caption("無匹配內容。")
                            continue
                        for i, (text, html) in enumerate(
                            zip(tag_result.contents, tag_result.html_snippets)
                        ):
                            st.markdown(
                                f"<div style='font-size:0.875rem;padding:5px 0;"
                                f"border-bottom:1px solid rgba(148,130,210,0.12)'>"
                                f"<span style='color:#7c6fa0;font-family:DM Mono,monospace;"
                                f"font-size:0.7rem'>#{i+1}</span>&nbsp;&nbsp;{text}</div>",
                                unsafe_allow_html=True,
                            )
                            if show_html:
                                st.code(html, language="html")


def _render_two_stage_pipeline_panel() -> None:
    """二階段工作流 UI 面板：列表頁 → 擷取連結 → 深度爬取詳情頁"""
    with st.container(border=True):
        st.markdown(
            '<div class="panel-title">🔗 二階段工作流（列表頁 → 詳情頁）</div>',
            unsafe_allow_html=True,
        )

        # ── Stage 1 設定 ──────────────────────────────────
        st.markdown(
            '<div class="pipeline-stage-header stage1-header">🟦 Stage 1 — 列表頁（擷取連結）</div>',
            unsafe_allow_html=True,
        )

        col_url1, col_sel1 = st.columns([3, 2])
        with col_url1:
            list_url = st.text_input(
                "列表頁 URL",
                placeholder="https://example.com/products",
                key="pipeline_list_url",
                help="要爬取的商品列表頁或文章列表頁網址",
            )
        with col_sel1:
            s1_selector = st.text_input(
                "連結 Selector",
                placeholder="a.product-link",
                key="pipeline_s1_selector",
                help="指向 <a> 標籤的 CSS selector，系統自動抓取 href 屬性",
            )

        col_b1, col_sc1 = st.columns(2)
        with col_b1:
            s1_browser = st.checkbox(
                "🌐 瀏覽器渲染",
                key="pipeline_s1_browser",
                help="列表頁若是 JS 動態渲染（如蝦皮、momo）請開啟",
            )
        with col_sc1:
            s1_scroll = st.checkbox(
                "📜 自動捲動",
                key="pipeline_s1_scroll",
                disabled=not s1_browser,
                help="捲動到底部觸發 lazy-load，適合商品列表",
            )

        st.divider()

        # ── Stage 2 設定 ──────────────────────────────────
        st.markdown(
            '<div class="pipeline-stage-header stage2-header">🟩 Stage 2 — 詳情頁（深度擷取）</div>',
            unsafe_allow_html=True,
        )
        st.caption("設定從每個詳情頁要擷取的欄位，可新增多筆（如標題、價格、描述等）")

        if "pipeline_s2_queries" not in st.session_state:
            st.session_state["pipeline_s2_queries"] = [{"selector": "", "attribute": ""}]

        s2_queries = st.session_state["pipeline_s2_queries"]

        for i, q in enumerate(s2_queries):
            col_s, col_a, col_d = st.columns([3, 2, 1], vertical_alignment="bottom")
            with col_s:
                q["selector"] = st.text_input(
                    f"S2 Selector #{i+1}",
                    value=q["selector"],
                    placeholder="h1.title 或 span.price",
                    key=f"pipeline_s2_sel_{i}",
                    label_visibility="collapsed" if i > 0 else "visible",
                )
            with col_a:
                q["attribute"] = st.text_input(
                    f"S2 Attribute #{i+1}",
                    value=q["attribute"],
                    placeholder="留空=文字 / href / src",
                    key=f"pipeline_s2_attr_{i}",
                    label_visibility="collapsed" if i > 0 else "visible",
                )
            with col_d:
                if st.button("✕", key=f"pipeline_s2_del_{i}", disabled=len(s2_queries) == 1):
                    s2_queries.pop(i)
                    st.rerun()

        col_add2, _ = st.columns([1, 3])
        with col_add2:
            if st.button("＋ 新增欄位", key="pipeline_s2_add", width="stretch"):
                s2_queries.append({"selector": "", "attribute": ""})
                st.rerun()

        col_b2, col_sc2, col_dom, col_mp = st.columns(4)
        with col_b2:
            s2_browser = st.checkbox(
                "🌐 瀏覽器渲染",
                key="pipeline_s2_browser",
                help="詳情頁若是 JS 動態渲染請開啟",
            )
        with col_sc2:
            s2_scroll = st.checkbox(
                "📜 自動捲動",
                key="pipeline_s2_scroll",
                disabled=not s2_browser,
            )
        with col_dom:
            same_domain = st.checkbox(
                "🔒 限同網域",
                value=True,
                key="pipeline_same_domain",
                help="只爬取與列表頁同網域的連結（強烈建議保持開啟）",
            )
        with col_mp:
            max_pages = st.number_input(
                "最多詳情頁數",
                min_value=1,
                max_value=50,
                value=10,
                key="pipeline_max_pages",
                help="Stage 2 最多爬取幾個詳情頁，防止無限爬取",
            )

        # ── 執行按鈕 ──────────────────────────────────────
        col_run_btn, col_clear_btn = st.columns([3, 1])
        with col_run_btn:
            run_pipeline_btn = st.button(
                "🚀 執行工作流",
                type="primary",
                width="stretch",
                key="pipeline_run_btn",
            )
        with col_clear_btn:
            if st.button("清除結果", width="stretch", key="pipeline_clear_btn"):
                if "pipeline_result" in st.session_state:
                    del st.session_state["pipeline_result"]
                st.rerun()

    # ── 執行邏輯 ──────────────────────────────────────────
    if run_pipeline_btn:
        valid_s2 = [
            (q["selector"], q["attribute"])
            for q in s2_queries
            if q["selector"].strip()
        ]
        if not list_url:
            st.warning("請輸入列表頁 URL")
        elif not s1_selector:
            st.warning("請輸入 Stage 1 的連結 Selector")
        elif not valid_s2:
            st.warning("請至少設定一個 Stage 2 擷取條件")
        else:
            stage1_cfg = StageConfig(
                selectors=[(s1_selector, "href")],
                label="Stage 1 - 列表頁",
                use_browser=s1_browser,
                scroll_to_bottom=s1_scroll,
            )
            stage2_cfg = StageConfig(
                selectors=valid_s2,
                label="Stage 2 - 詳情頁",
                use_browser=s2_browser,
                scroll_to_bottom=s2_scroll,
            )
            # Stage 2 用保守設定：低並發 + 高延遲，對目標網站友善
            crawler_cfg = CrawlerConfig(
                max_concurrency=2,
                request_delay=2.0,
                timeout=15.0,
                respect_robots=True,
            )

            progress_bar = st.progress(0)
            status_text = st.empty()
            status_text.markdown(
                '<p style="font-size:0.8rem;color:#64748b;font-family:DM Mono,monospace">準備執行工作流...</p>',
                unsafe_allow_html=True,
            )

            def on_progress(current: int, total: int, url: str) -> None:
                pct = current / total if total > 0 else 0
                progress_bar.progress(pct)
                status_text.markdown(
                    f'<p style="font-size:0.8rem;color:#64748b;font-family:DM Mono,monospace">'
                    f'Stage 2 [{current}/{total}] 正在爬取：{url[:65]}...</p>',
                    unsafe_allow_html=True,
                )

            with st.spinner("工作流執行中，請稍候..."):
                pipeline_result = run_two_stage_pipeline_sync(
                    source_url=list_url,
                    stage1_cfg=stage1_cfg,
                    stage2_cfg=stage2_cfg,
                    crawler_cfg=crawler_cfg,
                    same_domain_only=same_domain,
                    max_detail_pages=int(max_pages),
                    progress_callback=on_progress,
                )

            progress_bar.progress(1.0)
            st.session_state["pipeline_result"] = pipeline_result

    # ── 結果渲染 ──────────────────────────────────────────
    if "pipeline_result" in st.session_state:
        res: TwoStagePipelineResult = st.session_state["pipeline_result"]

        if res.error:
            st.error(f"❌ 工作流失敗：{res.error}")
        else:
            n_ok = sum(1 for r in res.stage2_results if not r.error)
            n_fail = len(res.stage2_results) - n_ok
            st.success(
                f"✅ 工作流完成 · "
                f"擷取連結 {len(res.extracted_links)} 條 · "
                f"詳情頁成功 {n_ok} / 失敗 {n_fail} · "
                f"總耗時 {res.total_fetch_time_ms / 1000:.1f}s"
            )

            # ── Stage 1 連結預覽 ──
            with st.expander(f"📋 Stage 1 擷取的連結（共 {len(res.extracted_links)} 筆）"):
                for link in res.extracted_links:
                    st.markdown(
                        f"<div class='pipeline-link-item'>{link}</div>",
                        unsafe_allow_html=True,
                    )

            # ── Stage 2 詳情頁結果 ──
            st.markdown(
                "<p style='font-size:0.8rem;font-weight:700;color:#065f46;"
                "margin:1rem 0 0.5rem'>Stage 2 詳情頁結果</p>",
                unsafe_allow_html=True,
            )

            for page_result in res.stage2_results:
                status_icon = "❌" if page_result.error else "✅"
                short_url = page_result.source_url
                if len(short_url) > 80:
                    short_url = short_url[:77] + "..."

                with st.expander(f"{status_icon} {short_url}  ({page_result.fetch_time_ms} ms)"):
                    if page_result.error:
                        st.error(page_result.error)
                        continue

                    for tag_res in page_result.tag_results:
                        attr_label = tag_res.attribute if tag_res.attribute else "文字"
                        st.markdown(
                            f"<p style='font-size:0.72rem;font-family:DM Mono,monospace;"
                            f"color:#7c6fa0;margin:0.5rem 0 0.2rem'>"
                            f"<b style='color:#1e1b4b'>`{tag_res.selector}`</b>"
                            f" [{attr_label}] — {len(tag_res.contents)} 筆</p>",
                            unsafe_allow_html=True,
                        )
                        for content in tag_res.contents[:8]:
                            st.markdown(
                                f"<div style='font-size:0.83rem;padding:4px 10px;"
                                f"border-left:3px solid #8b5cf6;margin:3px 0;"
                                f"background:rgba(139,92,246,0.04);border-radius:0 4px 4px 0'>"
                                f"{content}</div>",
                                unsafe_allow_html=True,
                            )

            # ── Pipeline 匯出 ──
            if res.stage2_results:
                st.markdown("---")
                st.markdown(
                    '<div class="panel-title">匯出 Pipeline 結果</div>',
                    unsafe_allow_html=True,
                )
                pipeline_df = _pipeline_results_to_dataframe(res)

                dl1, dl2 = st.columns(2)
                with dl1:
                    st.download_button(
                        label="📥 下載 CSV",
                        data=pipeline_df.to_csv(index=False).encode("utf-8-sig"),
                        file_name=f"pipeline_results_{int(time.time())}.csv",
                        mime="text/csv",
                        width="stretch",
                    )
                with dl2:
                    st.download_button(
                        label="📥 下載 JSON",
                        data=pipeline_df.to_json(
                            orient="records", force_ascii=False, indent=2
                        ).encode("utf-8"),
                        file_name=f"pipeline_results_{int(time.time())}.json",
                        mime="application/json",
                        width="stretch",
                    )

                with st.expander("📊 查看完整 Pipeline 資料表"):
                    st.dataframe(pipeline_df, width="stretch", height=400)


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
        st.session_state["crawl_history"] = []
    if "sb_filter" not in st.session_state:
        st.session_state["sb_filter"] = "全部"

    # ── Sidebar ──────────────────────────────────────────
    with st.sidebar:

        st.markdown(
            """
        <div style='padding:1rem 0 0.5rem;border-bottom:1px solid rgba(148,130,210,0.22);margin-bottom:0.5rem'>
            <div style='font-size:1.1rem;font-weight:800;font-family:Syne,sans-serif;
                        background:linear-gradient(90deg,#8b5cf6,#ec4899);
                        -webkit-background-clip:text;-webkit-text-fill-color:transparent'>
                🕸 Crawler
            </div>
            <div style='font-size:0.62rem;color:#7c6fa0;font-family:DM Mono,monospace;margin-top:2px'>
                StProject · v1.1
            </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

        # ── 爬蟲參數 ──
        st.markdown(
            '<div class="sb-section"><div class="sb-section-title">爬蟲參數</div></div>',
            unsafe_allow_html=True,
        )
        concurrency = st.slider("⚡ 並發數", min_value=1, max_value=8, value=3,
                                help="同時爬取的連結數，建議 ≤ 5")
        delay = st.slider("⏱ 請求間隔（秒）", min_value=0.5, max_value=5.0,
                          value=1.5, step=0.5, help="每次請求的等待時間，值越高對目標越友善")
        timeout = st.slider("⌛ 逾時上限（秒）", min_value=5, max_value=30,
                            value=15, help="單頁最長等待時間")
        max_urls = st.slider("📋 單批上限", min_value=5, max_value=50,
                             value=20, step=5, help="單次爬取的 URL 數量上限")

        # ── 內容設定 ──
        st.markdown(
            '<div class="sb-section"><div class="sb-section-title">內容設定</div></div>',
            unsafe_allow_html=True,
        )
        content_mode = st.selectbox(
            "🎯 內容類型",
            ["自動偵測", "僅商品", "僅影片"],
            help="強制指定解析模式，或讓系統自動判斷",
        )
        max_tags = st.slider("🏷 標籤數量上限", min_value=3, max_value=20,
                             value=10, help="每筆結果保留的標籤數量")
        include_thumbnail = st.checkbox("縮圖連結", value=True,
                                        help="是否擷取 og:image 縮圖 URL")

        # ── 合規控制 ──
        st.markdown(
            '<div class="sb-section"><div class="sb-section-title">合規控制</div></div>',
            unsafe_allow_html=True,
        )
        respect_robots = st.checkbox("遵守 robots.txt", value=True,
                                     help="建議保持開啟，自動跳過禁止爬取的頁面")
        enable_dedup = st.checkbox("URL 去重複", value=True,
                                   help="自動移除重複的輸入 URL")
        strip_personal = st.checkbox("個資自動過濾", value=True,
                                     help="自動遮蔽結果中的電話、Email 等個人資料")

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

        # ── 結果快篩 ──
        if "crawl_results" in st.session_state:
            results_snapshot = st.session_state["crawl_results"]
            n_total = len(results_snapshot)
            n_product = sum(1 for r in results_snapshot if r.content_type == ContentType.PRODUCT)
            n_video = sum(1 for r in results_snapshot if r.content_type == ContentType.VIDEO)
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

        # ── 爬取歷史 ──
        history = st.session_state.get("crawl_history", [])
        if history:
            st.markdown(
                '<div class="sb-section"><div class="sb-section-title">爬取歷史</div></div>',
                unsafe_allow_html=True,
            )
            for rec in reversed(history[-5:]):
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
            if st.button("🗑  清除歷史", width="stretch"):
                st.session_state["crawl_history"] = []
                st.rerun()

    # ── 主內容區 ──────────────────────────────────────────
    col_input, col_preview = st.columns([3, 2], gap="large")

    with col_input:
        st.markdown('<div class="panel-title">目標 URL 輸入</div>', unsafe_allow_html=True)
        url_input = st.text_area(
            "URLs",
            height=200,
            placeholder="每行輸入一個 URL，例如：\nhttps://shopee.tw/product/xxx\nhttps://www.youtube.com/watch?v=xxx",
            label_visibility="collapsed",
        )
        col_btn, col_clear = st.columns([2, 1])
        with col_btn:
            start_btn = st.button("🚀  開始爬取", width="stretch")
        with col_clear:
            if st.button("清除結果", width="stretch"):
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

            # 套用 content_mode 強制覆蓋類型
            if content_mode == "僅商品":
                for r in results:
                    if not r.error:
                        r.content_type = ContentType.PRODUCT
            elif content_mode == "僅影片":
                for r in results:
                    if not r.error:
                        r.content_type = ContentType.VIDEO

            # 截斷標籤數量
            for r in results:
                r.tags = r.tags[:max_tags]

            # 移除縮圖（若未勾選）
            if not include_thumbnail:
                for r in results:
                    r.thumbnail_url = None

            # 個資過濾
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

        # ── 自訂 Tag 擷取面板 ──
        st.divider()
        _render_tag_extractor_panel()

        # ── 二階段工作流面板 ──
        st.divider()
        _render_two_stage_pipeline_panel()

        # ── 匯出資料 ──
        st.markdown('<div class="panel-title">匯出資料</div>', unsafe_allow_html=True)
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="📥  下載 CSV",
                data=df.to_csv(index=False).encode("utf-8-sig"),
                file_name=f"crawl_results_{int(time.time())}.csv",
                mime="text/csv",
                width="stretch",
            )
        with dl_col2:
            st.download_button(
                label="📥  下載 JSON",
                data=df.to_json(orient="records", force_ascii=False, indent=2).encode("utf-8"),
                file_name=f"crawl_results_{int(time.time())}.json",
                mime="application/json",
                width="stretch",
            )

        with st.expander("📊 查看完整資料表"):
            st.dataframe(df, width="stretch", height=400)

    else:
        # 尚無爬取結果時也顯示工作流面板（讓使用者可以直接使用 Pipeline）
        st.divider()
        _render_tag_extractor_panel()
        st.divider()
        _render_two_stage_pipeline_panel()


# 直接執行時使用
if __name__ == "__main__":
    show()
