"""Extract main content text from HTML (readability-lxml preferred, BeautifulSoup fallback)."""

from typing import Tuple


def extract_main_text(html: str) -> Tuple[str, str]:
    """
    Extract main content text from HTML.

    Prefers readability-lxml; falls back to BeautifulSoup (body text).
    Returns (extracted_text, method_used).
    """
    if not html or not html.strip():
        return "", "empty"

    # Try readability-lxml first
    try:
        from readability import Document
        doc = Document(html)
        title = doc.title() or ""
        content = doc.summary() or ""
        # Strip HTML tags from summary (readability returns HTML)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "lxml")
        text = soup.get_text(separator=" ", strip=True)
        # Normalize whitespace
        text = " ".join(text.split())
        if text:
            return text, "readability-lxml"
    except Exception:
        pass

    # Fallback: BeautifulSoup body text
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        body = soup.find("body") or soup
        text = body.get_text(separator=" ", strip=True)
        text = " ".join(text.split())
        return text or "", "beautifulsoup"
    except Exception:
        pass

    return "", "none"
