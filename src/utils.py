"""Utilities for partner-portrayal-scanner: safe filenames, run IDs, paths."""

import re
import uuid
from pathlib import Path
from typing import Optional


# Default user-agent for polite crawling
DEFAULT_USER_AGENT = (
    "PartnerPortrayalScanner/1.0 (compliance-monitoring; +https://example.com/bot)"
)

# Polite crawling: sleep between requests (seconds)
RATE_LIMIT_SLEEP = 0.5


def safe_filename(url: str, max_length: int = 200) -> str:
    """
    Produce a filesystem-safe base name from a URL for evidence files.

    Replaces unsafe characters, truncates to max_length, and ensures
    a non-empty result (fallback to a short hash-like suffix).
    """
    if not url or not url.strip():
        return f"unknown_{uuid.uuid4().hex[:8]}"
    # Use only path + normalized host; strip scheme and fragment
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        netloc = parsed.netloc or "unknown"
        path = (parsed.path or "").strip("/") or "index"
        raw = f"{netloc}_{path}"
    except Exception:
        raw = url
    # Replace unsafe chars with underscore
    safe = re.sub(r"[^\w\-.]", "_", raw, flags=re.ASCII)
    safe = re.sub(r"_+", "_", safe).strip("_")
    if not safe:
        safe = f"page_{uuid.uuid4().hex[:8]}"
    if len(safe) > max_length:
        safe = safe[:max_length].rstrip("_")
    return safe or f"page_{uuid.uuid4().hex[:8]}"


def generate_run_id() -> str:
    """Return a short unique run identifier (ISO date + short UUID)."""
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"{ts}_{uuid.uuid4().hex[:8]}"


def ensure_evidence_dirs(base_dir: Path) -> tuple[Path, Path, Path]:
    """
    Ensure evidence subdirs exist: raw_html, extracted_text, meta.
    Returns (raw_html_path, extracted_text_path, meta_path).
    """
    raw = base_dir / "raw_html"
    text = base_dir / "extracted_text"
    meta = base_dir / "meta"
    raw.mkdir(parents=True, exist_ok=True)
    text.mkdir(parents=True, exist_ok=True)
    meta.mkdir(parents=True, exist_ok=True)
    return raw, text, meta
