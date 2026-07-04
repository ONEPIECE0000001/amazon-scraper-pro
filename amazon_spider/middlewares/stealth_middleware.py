from playwright_stealth import Stealth
from scrapy_playwright.page import PageMethod


class PlaywrightStealthMiddleware:
    """Injects playwright-stealth init scripts into every Playwright page.

    Uses Stealth().script_payload (a combined IIFE of all evasion scripts)
    and registers it as a page init script via PageMethod("add_init_script", ...).
    This ensures the evasion JS runs on every page navigation before any site
    script executes.
    """

    def __init__(self):
        self.stealth_js = Stealth(chrome_runtime=False).script_payload

    def process_request(self, request, spider):
        if not request.meta.get("playwright"):
            return

        coroutines = request.meta.setdefault("playwright_page_coroutines", [])
        coroutines.insert(0, PageMethod("add_init_script", self.stealth_js))
        spider.logger.debug("Stealth init script injected for %s", request.url)
