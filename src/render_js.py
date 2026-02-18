"""Optional: fetch page with Playwright for JS-rendered content."""

from pathlib import Path
from typing import Optional

try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    sync_playwright = None  # type: ignore


def render_with_playwright(
    url: str,
    timeout: int = 25000,
    screenshot_path: Optional[Path] = None,
) -> "FetchResult":
    """
    Fetch URL with Playwright, wait for network idle, return HTML and metadata.
    If screenshot_path is set, save a full-page screenshot of the page.
    Raises if Playwright is not installed.
    """
    from src.fetch import FetchResult
    if not PLAYWRIGHT_AVAILABLE or sync_playwright is None:
        raise RuntimeError("Playwright not installed. pip install playwright && playwright install")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=timeout)
            html = page.content()
            title = page.title() or None
            final_url = page.url
            if screenshot_path:
                screenshot_path = Path(screenshot_path)
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(screenshot_path), full_page=True)
            browser.close()
            return FetchResult(
                url=url,
                final_url=final_url,
                status_code=200,
                html=html,
                title=title,
            )
        except Exception as e:
            try:
                browser.close()
            except Exception:
                pass
            return FetchResult(
                url=url,
                final_url=url,
                status_code=-1,
                html="",
                error=str(e),
            )
