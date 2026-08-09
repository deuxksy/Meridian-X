import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

TARGET_DOMAINS = ["mediafire.com", "mega.nz", "gofile.io", "pixeldrain.com"]


class OuoBypasser:
    async def resolve(self, short_url: str) -> str:
        return await self._run_playwright_bypass(short_url)

    async def _run_playwright_bypass(self, short_url: str) -> str:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            target_url = short_url

            def check_and_update_url(url: str):
                nonlocal target_url
                if any(domain in url for domain in TARGET_DOMAINS):
                    target_url = url

            def on_response(response):
                check_and_update_url(response.url)

            def on_request(request):
                check_and_update_url(request.url)

            page.on("response", on_response)
            page.on("request", on_request)

            try:
                await page.goto(short_url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(1000)

                # Fallback for ouo.io form buttons
                for _ in range(2):
                    if any(domain in target_url for domain in TARGET_DOMAINS):
                        break

                    btn = (
                        await page.query_selector("#btn-main")
                        or await page.query_selector("form button")
                        or await page.query_selector("button[type='submit']")
                    )
                    if btn and await btn.is_visible():
                        await btn.click()
                        await page.wait_for_timeout(2000)
                    else:
                        break

                check_and_update_url(page.url)

            except Exception as e:
                logger.warning(f"Error during Playwright bypass for {short_url}: {e}")
            finally:
                await browser.close()

            return target_url
