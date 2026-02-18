#!/usr/bin/env python3
"""
Mark false positives and append suppressions to policy.yml so future runs have better detection.

Workflow:
  1. Run scan: python scan.py --urls urls.txt --policy policy.yml
  2. Open report.csv, find rows that are false positives
  3. Create false_positive_marks.csv with one row per false positive (see format below)
  4. Run: python mark_false_positives.py --marks false_positive_marks.csv --append-policy
  5. Re-run scan; those findings will be suppressed

Marks file (CSV) columns:
  url          - page URL (or substring of it for url_contains)
  rule_id      - rule to suppress (e.g. DISC_001_APR_MENTION_EXPECTED)
  snippet_contains - optional: only suppress when snippet contains this text
  match_contains   - optional: only suppress when match_text contains this text
  url_contains - optional: only suppress when URL contains this (default: from url column)
  reason       - optional: for documentation in policy
"""

import argparse
import csv
import sys
from pathlib import Path

import yaml

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent))


def load_marks(marks_path: Path) -> list[dict]:
    """Load marks CSV; return list of dicts with keys rule_id, url_contains?, snippet_contains?, match_contains?, reason?."""
    rows = []
    with open(marks_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rule_id = (row.get("rule_id") or "").strip()
            if not rule_id:
                continue
            entry = {"rule_id": rule_id}
            url = (row.get("url") or "").strip()
            if url:
                entry["url_contains"] = url
            sc = (row.get("snippet_contains") or "").strip()
            if sc:
                entry["snippet_contains"] = sc
            mc = (row.get("match_contains") or "").strip()
            if mc:
                entry["match_contains"] = mc
            uc = (row.get("url_contains") or "").strip()
            if uc:
                entry["url_contains"] = uc
            reason = (row.get("reason") or "").strip()
            if reason:
                entry["reason"] = reason
            rows.append(entry)
    return rows


def load_policy(policy_path: Path) -> dict:
    with open(policy_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def append_suppressions_to_policy(policy_path: Path, new_suppressions: list[dict]) -> None:
    """Append new_suppressions to policy's suppressions list via text replace (preserves rest of file)."""
    policy = load_policy(policy_path)
    existing = policy.get("suppressions") or []
    seen = {(s.get("rule_id"), s.get("snippet_contains"), s.get("match_contains"), s.get("url_contains")) for s in existing}
    to_add = []
    for s in new_suppressions:
        key = (s.get("rule_id"), s.get("snippet_contains"), s.get("match_contains"), s.get("url_contains"))
        if key in seen:
            continue
        to_add.append(s)
        seen.add(key)
    if not to_add:
        return
    block = yaml.safe_dump(to_add, default_flow_style=False, allow_unicode=True, sort_keys=False)
    # Indent so it sits under suppressions:
    indented = "".join("  " + line for line in block.splitlines(keepends=True))
    text = policy_path.read_text(encoding="utf-8")
    if "suppressions: []" in text:
        text = text.replace("suppressions: []", "suppressions:\n" + indented.rstrip())
    else:
        # Already has entries; append (simple: replace first "suppressions:" line and list)
        import re
        match = re.search(r"suppressions:\s*\n((?:\s+-\s+.*\n?)*)", text)
        if match:
            existing_block = match.group(0)
            new_block = "suppressions:\n" + existing_block.split("\n", 1)[1].rstrip() + "\n" + indented
            text = text.replace(existing_block, new_block)
        else:
            # Fallback: load, merge, dump (may change formatting)
            policy["suppressions"] = existing + to_add
            policy_path.write_text(yaml.safe_dump(policy, default_flow_style=False, allow_unicode=True, sort_keys=False), encoding="utf-8")
            return
    policy_path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Mark false positives and append suppressions to policy.yml")
    parser.add_argument("--marks", type=Path, default=Path("false_positive_marks.csv"), help="CSV of false-positive marks")
    parser.add_argument("--policy", type=Path, default=Path("policy.yml"), help="Policy file to update")
    parser.add_argument("--append-policy", action="store_true", help="Append suppressions to policy and save")
    parser.add_argument("--print", action="store_true", dest="print_only", help="Only print YAML block to paste into policy")
    args = parser.parse_args()

    if not args.marks.exists():
        print(f"Error: Marks file not found: {args.marks}", file=sys.stderr)
        print("Create a CSV with columns: url, rule_id, snippet_contains (optional), match_contains (optional), url_contains (optional), reason (optional)", file=sys.stderr)
        return 1

    suppressions = load_marks(args.marks)
    if not suppressions:
        print("No valid rows in marks file (need at least rule_id).", file=sys.stderr)
        return 1

    if args.print_only:
        print("# Add this to policy.yml under suppressions:")
        print(yaml.safe_dump({"suppressions": suppressions}, default_flow_style=False, allow_unicode=True, sort_keys=False))
        return 0

    if not args.append_policy:
        print("Use --append-policy to update policy.yml, or --print to print YAML block.", file=sys.stderr)
        return 0

    if not args.policy.exists():
        print(f"Error: Policy not found: {args.policy}", file=sys.stderr)
        return 1

    append_suppressions_to_policy(args.policy, suppressions)
    print(f"Appended {len(suppressions)} suppression(s) to {args.policy}. Re-run scan to apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
