"""Fetch web pages with requests; optional JS rendering via Playwright."""

import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.utils import DEFAULT_USER_AGENT

# Polite crawling
REQUEST_TIMEOUT = 25
RETRY_SLEEP = 1.0
RATE_LIMIT_SLEEP = 0.5


@dataclass
class FetchResult:
    """Result of fetching a URL."""

    url: str
    final_url: str
    status_code: int
    html: str
    title: Optional[str] = None
    error: Optional[str] = None


def fetch_with_requests(
    url: str,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: int = REQUEST_TIMEOUT,
) -> FetchResult:
    """
    Fetch URL with requests. One retry on failure.
    Does not follow redirects beyond a reasonable limit (handled by requests).
    """
    import requests
    session = requests.Session()
    session.headers["User-Agent"] = user_agent
    last_error: Optional[str] = None
    for attempt in range(2):
        try:
            resp = session.get(url, timeout=timeout, allow_redirects=True)
            # Best-effort title from HTML
            title = None
            if resp.text:
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text[:50000], "lxml")
                    t = soup.find("title")
                    if t and t.string:
                        title = t.string.strip()[:500]
                except Exception:
                    pass
            return FetchResult(
                url=url,
                final_url=resp.url,
                status_code=resp.status_code,
                html=resp.text,
                title=title,
            )
        except requests.RequestException as e:
            last_error = str(e)
            if attempt == 0:
                time.sleep(RETRY_SLEEP)
    return FetchResult(
        url=url,
        final_url=url,
        status_code=-1,
        html="",
        error=last_error,
    )


def fetch_url(
    url: str,
    use_playwright: bool = False,
    user_agent: str = DEFAULT_USER_AGENT,
    timeout: int = REQUEST_TIMEOUT,
    rate_limit_sleep: float = RATE_LIMIT_SLEEP,
    screenshot_path: Optional[Path] = None,
) -> FetchResult:
    """
    Fetch a single URL. If use_playwright is True, try render_js; else use requests.
    When use_playwright and screenshot_path is set, a full-page screenshot is saved.
    Caller should sleep rate_limit_sleep between calls when scanning multiple URLs.
    """
    if use_playwright:
        try:
            from src.render_js import render_with_playwright
            return render_with_playwright(url, timeout=timeout, screenshot_path=screenshot_path)
        except Exception:
            return fetch_with_requests(url, user_agent=user_agent, timeout=timeout)
    return fetch_with_requests(url, user_agent=user_agent, timeout=timeout)
