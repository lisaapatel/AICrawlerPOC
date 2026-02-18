#!/usr/bin/env python3
"""
Partner Portrayal Scanner — scan partner webpages for risky/misleading portrayal.
Usage:
  python scan.py --urls urls.txt --policy policy.yml [--render js] [--evidence-dir evidence]
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.extract import extract_main_text
from src.fetch import fetch_url, FetchResult
from src.report import ScanResult, write_csv, write_evidence, write_html_report
from src.rules import run_rules
from src.utils import RATE_LIMIT_SLEEP, ensure_evidence_dirs, generate_run_id, safe_filename


def load_urls(urls_path: Path) -> list[str]:
    """Load URLs from file (one per line, skip empty and # comments)."""
    lines = urls_path.read_text(encoding="utf-8").splitlines()
    return [u.strip() for u in lines if u.strip() and not u.strip().startswith("#")]


def main() -> int:
    parser = argparse.ArgumentParser(description="Partner Portrayal Scanner")
    parser.add_argument("--urls", type=Path, default=Path("urls.txt"), help="Path to urls.txt")
    parser.add_argument("--policy", type=Path, default=Path("policy.yml"), help="Path to policy.yml")
    parser.add_argument("--evidence-dir", type=Path, default=Path("evidence"), help="Evidence output directory")
    parser.add_argument("--render", choices=["js"], default=None, help="Use Playwright for JS rendering")
    parser.add_argument("--no-evidence", action="store_true", help="Skip writing evidence files")
    args = parser.parse_args()

    if not args.urls.exists():
        print(f"Error: URLs file not found: {args.urls}", file=sys.stderr)
        return 1
    if not args.policy.exists():
        print(f"Error: Policy file not found: {args.policy}", file=sys.stderr)
        return 1

    urls = load_urls(args.urls)
    if not urls:
        print("No URLs to scan.", file=sys.stderr)
        return 0

    use_playwright = args.render == "js"
    run_id = generate_run_id()
    scanned_at_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    evidence_dir = args.evidence_dir
    if not args.no_evidence:
        ensure_evidence_dirs(evidence_dir)
    if use_playwright and not args.no_evidence:
        (evidence_dir / "screenshots").mkdir(parents=True, exist_ok=True)

    results_for_report: list[tuple[ScanResult, str, str, Optional[str]]] = []

    for i, url in enumerate(urls):
        if i > 0:
            import time
            time.sleep(RATE_LIMIT_SLEEP)

        safe_basename = safe_filename(url)
        screenshot_path: Optional[Path] = None
        screenshot_rel: Optional[str] = None
        if use_playwright and not args.no_evidence:
            screenshot_path = evidence_dir / "screenshots" / f"{safe_basename}.png"
            screenshot_rel = str(evidence_dir / "screenshots" / f"{safe_basename}.png")

        fetch_result: FetchResult = fetch_url(
            url, use_playwright=use_playwright, screenshot_path=screenshot_path
        )
        fetch_time_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        if fetch_result.error:
            scan_result = ScanResult(
                url=url,
                final_url=fetch_result.final_url,
                http_status=fetch_result.status_code,
                title=fetch_result.title,
                findings=[],
                error=fetch_result.error,
            )
            extracted_text = ""
            screenshot_rel = None
        else:
            extracted_text, _ = extract_main_text(fetch_result.html)
            findings = run_rules(
                extracted_text,
                args.policy,
                page_url=fetch_result.final_url or url,
            )
            scan_result = ScanResult(
                url=url,
                final_url=fetch_result.final_url,
                http_status=fetch_result.status_code,
                title=fetch_result.title,
                findings=findings,
            )
            if not (screenshot_path and screenshot_path.exists()):
                screenshot_rel = None

        results_for_report.append((scan_result, extracted_text, safe_basename, screenshot_rel))

        if not args.no_evidence and not fetch_result.error:
            write_evidence(
                evidence_dir,
                safe_basename,
                url=url,
                final_url=fetch_result.final_url,
                http_status=fetch_result.status_code,
                title=fetch_result.title,
                raw_html=fetch_result.html,
                extracted_text=extracted_text,
                fetch_time_iso=fetch_time_iso,
            )
        if fetch_result.error:
            print(f"Warning: {url} — {fetch_result.error}", file=sys.stderr)

    # CSV and HTML reports (always in cwd unless we add args)
    report_csv = Path("report.csv")
    report_html = Path("report.html")
    write_csv(results_for_report, report_csv, run_id, scanned_at_iso)
    write_html_report(results_for_report, report_html, run_id, scanned_at_iso)
    print(f"Run ID: {run_id}")
    print(f"Report: {report_csv}, {report_html}")
    if not args.no_evidence:
        print(f"Evidence: {evidence_dir}/")
    total_findings = sum(len(r[0].findings) for r in results_for_report)
    print(f"Total findings: {total_findings}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
