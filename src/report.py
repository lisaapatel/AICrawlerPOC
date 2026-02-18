"""Report generation: CSV, HTML, and evidence files."""

import csv
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from src.rules import Finding


@dataclass
class ScanResult:
    """Result of scanning one URL: metadata + list of findings."""

    url: str
    final_url: str
    http_status: int
    title: Optional[str]
    findings: list[Finding]
    error: Optional[str] = None


CSV_COLUMNS = [
    "run_id",
    "scanned_at_iso",
    "url",
    "final_url",
    "http_status",
    "title",
    "rule_id",
    "taxonomy",
    "severity",
    "match_text",
    "snippet",
    "recommendation",
    "page_url",
    "screenshot",
]


def _escape_csv(val: Optional[str]) -> str:
    """Escape a value for CSV (quotes and internal quotes)."""
    if val is None:
        return ""
    s = str(val)
    if '"' in s or "\n" in s or "," in s:
        return '"' + s.replace('"', '""') + '"'
    return s


def write_csv(
    results: list[tuple[ScanResult, str, str, Optional[str]]],
    output_path: Path,
    run_id: str,
    scanned_at_iso: str,
) -> None:
    """
    Write report.csv. results is list of (ScanResult, extracted_text, safe_basename, screenshot_rel).
    Each finding becomes one row. page_url = final_url (link to webpage); screenshot = path to PNG if any.
    """
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(CSV_COLUMNS)
        for scan_result, _extracted, _base, screenshot_rel in results:
            page_url = scan_result.final_url or scan_result.url
            for finding in scan_result.findings:
                w.writerow([
                    run_id,
                    scanned_at_iso,
                    scan_result.url,
                    scan_result.final_url,
                    scan_result.http_status,
                    scan_result.title or "",
                    finding.rule_id,
                    finding.taxonomy,
                    finding.severity,
                    finding.match_text,
                    finding.snippet,
                    finding.recommendation,
                    page_url,
                    screenshot_rel or "",
                ])


def write_html_report(
    results: list[tuple[ScanResult, str, str, Optional[str]]],
    output_path: Path,
    run_id: str,
    scanned_at_iso: str,
) -> None:
    """
    Write report.html grouping findings per URL with highlighted match text.
    Includes page link and screenshot (if available from --render js run).
    """
    html_parts = [
        "<!DOCTYPE html>",
        "<html><head><meta charset='utf-8'><title>Partner Portrayal Scanner Report</title>",
        "<style>",
        "body { font-family: system-ui, sans-serif; margin: 1rem 2rem; }",
        "h1 { font-size: 1.25rem; }",
        "h2 { font-size: 1rem; margin-top: 1.5rem; }",
        ".url { word-break: break-all; color: #055; }",
        ".page-link { display: inline-block; margin: 0.25rem 0; padding: 0.25rem 0.5rem; background: #e8f4f8; border-radius: 4px; }",
        ".screenshot-wrap { margin: 0.75rem 0; }",
        ".screenshot-wrap img { max-width: 100%; width: 800px; height: auto; border: 1px solid #ccc; border-radius: 4px; }",
        ".finding { margin: 0.5rem 0; padding: 0.5rem; background: #f5f5f5; border-radius: 4px; }",
        ".rule-id { font-weight: bold; }",
        ".severity-HIGH { border-left: 4px solid #c00; }",
        ".severity-MEDIUM { border-left: 4px solid #c90; }",
        ".match { background: #ff9; }",
        "pre.snippet { white-space: pre-wrap; font-size: 0.9rem; }",
        "</style></head><body>",
        f"<h1>Partner Portrayal Scanner Report</h1>",
        f"<p><strong>Run ID:</strong> {_html_escape(run_id)} | <strong>Scanned:</strong> {_html_escape(scanned_at_iso)}</p>",
    ]

    for scan_result, extracted_text, _base, screenshot_rel in results:
        page_url = scan_result.final_url or scan_result.url
        html_parts.append("<h2>URL</h2>")
        html_parts.append(
            f"<p><strong>Page link:</strong> <a class='page-link' href='{_html_escape(page_url)}' target='_blank' rel='noopener'>{_html_escape(page_url)}</a></p>"
        )
        if scan_result.final_url != scan_result.url and scan_result.url != page_url:
            html_parts.append(f"<p><strong>Requested URL:</strong> <span class='url'>{_html_escape(scan_result.url)}</span></p>")
        html_parts.append(f"<p>Status: {scan_result.http_status} | Title: {_html_escape(scan_result.title or '')}</p>")
        if screenshot_rel:
            html_parts.append(f"<div class='screenshot-wrap'><strong>Screenshot of page:</strong><br><img src='{_html_escape(screenshot_rel)}' alt='Screenshot of {_html_escape(page_url)}' /></div>")

        if scan_result.findings:
            html_parts.append("<h3>Findings</h3>")
            for f in scan_result.findings:
                snippet_highlighted = _html_escape(f.snippet).replace(
                    _html_escape(f.match_text),
                    f"<span class='match'>{_html_escape(f.match_text)}</span>",
                    1,
                )
                html_parts.append(
                    f"<div class='finding severity-{f.severity}'>"
                    f"<span class='rule-id'>{_html_escape(f.rule_id)}</span> [{f.severity}] {_html_escape(f.taxonomy)}<br>"
                    f"<pre class='snippet'>{snippet_highlighted}</pre>"
                    f"<p><strong>Recommendation:</strong> {_html_escape(f.recommendation)}</p></div>"
                )
        else:
            html_parts.append("<p>No findings.</p>")
        html_parts.append("<hr>")

    html_parts.append("</body></html>")
    output_path.write_text("".join(html_parts), encoding="utf-8")


def _html_escape(s: str) -> str:
    if not s:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def write_evidence(
    evidence_dir: Path,
    safe_basename: str,
    url: str,
    final_url: str,
    http_status: int,
    title: Optional[str],
    raw_html: str,
    extracted_text: str,
    fetch_time_iso: Optional[str] = None,
) -> None:
    """
    Write evidence files: raw_html/<base>.html, extracted_text/<base>.txt, meta/<base>.json.
    """
    raw_dir = evidence_dir / "raw_html"
    text_dir = evidence_dir / "extracted_text"
    meta_dir = evidence_dir / "meta"
    raw_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    (raw_dir / f"{safe_basename}.html").write_text(raw_html, encoding="utf-8")
    (text_dir / f"{safe_basename}.txt").write_text(extracted_text, encoding="utf-8")
    meta = {
        "title": title,
        "final_url": final_url,
        "status": http_status,
        "fetch_time": fetch_time_iso,
        "content_length": len(raw_html),
    }
    (meta_dir / f"{safe_basename}.json").write_text(
        json.dumps(meta, indent=2),
        encoding="utf-8",
    )
