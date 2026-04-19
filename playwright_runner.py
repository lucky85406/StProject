"""
playwright_runner.py
獨立執行的 Playwright 爬蟲腳本，透過 subprocess 從主程式呼叫。
接收 stdin 的 JSON 輸入，輸出 JSON 到 stdout。

輸入格式：
{
    "url": "https://...",
    "wait_selector": "body",
    "timeout_ms": 20000,
    "scroll_to_bottom": false
}

輸出格式：
{
    "html": "...",
    "final_url": "https://...",
    "error": null
}
"""

import sys
import json
import asyncio


async def main() -> None:
    raw = sys.stdin.read()
    params = json.loads(raw)

    url: str = params["url"]
    wait_selector: str = params.get("wait_selector", "body")
    timeout_ms: int = params.get("timeout_ms", 20000)
    scroll_to_bottom: bool = params.get("scroll_to_bottom", False)

    result = {"html": "", "final_url": url, "error": None}

    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="zh-TW",
                extra_http_headers={"Accept-Language": "zh-TW,zh;q=0.9"},
            )
            page = await context.new_page()

            # 攔截圖片/字體加速載入
            await page.route(
                "**/*.{png,jpg,jpeg,gif,webp,svg,woff,woff2,ttf,otf}",
                lambda route: route.abort(),
            )

            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)

            try:
                await page.wait_for_selector(wait_selector, timeout=timeout_ms)
            except Exception:
                pass  # timeout 就用當前 HTML

            if scroll_to_bottom:
                await page.evaluate(
                    """
                    async () => {
                        await new Promise(resolve => {
                            let total = document.body.scrollHeight;
                            let current = 0;
                            const step = 400;
                            const timer = setInterval(() => {
                                window.scrollBy(0, step);
                                current += step;
                                if (current >= total) {
                                    clearInterval(timer);
                                    resolve();
                                }
                            }, 100);
                        });
                    }
                """
                )
                await page.wait_for_timeout(1500)

            result["html"] = await page.content()
            result["final_url"] = page.url

            await context.close()
            await browser.close()

    except Exception as e:
        result["error"] = str(e)

    # 改成：強制用 utf-8 輸出到 stdout
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8") + b"\n")
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    asyncio.run(main())
