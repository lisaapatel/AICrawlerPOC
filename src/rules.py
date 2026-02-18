"""Rules engine: patterns, proximity, conditional, and trigger_patterns rules."""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml


@dataclass
class Finding:
    """A single rule finding."""

    rule_id: str
    taxonomy: str
    severity: str
    match_text: str
    snippet: str
    recommendation: str


def _load_policy(policy_path: Path) -> dict[str, Any]:
    """Load and return policy YAML as dict."""
    with open(policy_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_scan_config(policy: dict[str, Any]) -> dict[str, Any]:
    """Extract scan config with defaults."""
    scan = policy.get("scan") or {}
    return {
        "snippet_chars": scan.get("snippet_chars", 260),
        "qualifier_window_chars": scan.get("qualifier_window_chars", 400),
        "proximity_window_chars": scan.get("proximity_window_chars", 250),
        "case_insensitive": scan.get("case_insensitive", True),
        "upgrade_context_window_chars": scan.get("upgrade_context_window_chars", 0),
    }


def _build_qualifier_phrases(policy: dict[str, Any]) -> dict[str, list[str]]:
    """Build map qualifier_name -> list of phrase strings (for matching)."""
    qualifiers = policy.get("qualifiers") or {}
    return {k: [p for p in v if p] for k, v in qualifiers.items() if isinstance(v, list)}


def _is_upgrade_related(text: str, policy: dict[str, Any], case_insensitive: bool) -> bool:
    """
    Return True if the page content is Upgrade-related (mentions Upgrade or a company name variant).
    When require_upgrade_context is true, we only report findings on such pages.
    """
    if not text:
        return False
    org = policy.get("org") or {}
    variants = org.get("company_name_variants") or []
    if not variants:
        return True  # No constraint
    flags = re.IGNORECASE if case_insensitive else 0
    for phrase in variants:
        if not phrase:
            continue
        try:
            if re.search(re.escape(phrase), text, flags):
                return True
        except Exception:
            pass
    return False


def _has_upgrade_near_position(
    text: str,
    center: int,
    window_chars: int,
    policy: dict[str, Any],
    case_insensitive: bool,
) -> bool:
    """Return True if 'Upgrade' (or variant) appears within window_chars of center in text."""
    if not text or window_chars <= 0:
        return True  # No constraint
    window_text = _window_around(text, center, window_chars)
    return _is_upgrade_related(window_text, policy, case_insensitive)


def _suppression_matches(
    finding: Finding,
    page_url: str,
    suppression: dict[str, Any],
    case_insensitive: bool,
) -> bool:
    """Return True if this finding is suppressed by the given rule."""
    if suppression.get("rule_id") != finding.rule_id:
        return False
    flags = re.IGNORECASE if case_insensitive else 0
    url_contains = suppression.get("url_contains") or ""
    if url_contains and not re.search(re.escape(url_contains), page_url, flags):
        return False
    snippet_contains = suppression.get("snippet_contains") or ""
    if snippet_contains and not re.search(re.escape(snippet_contains), finding.snippet, flags):
        return False
    match_contains = suppression.get("match_contains") or ""
    if match_contains and not re.search(re.escape(match_contains), finding.match_text, flags):
        return False
    return True


def _apply_suppressions(
    findings: list[Finding],
    policy: dict[str, Any],
    page_url: str,
    case_insensitive: bool,
) -> list[Finding]:
    """Filter out findings that match any suppression in policy."""
    suppressions = policy.get("suppressions") or []
    if not suppressions:
        return findings
    out = []
    for f in findings:
        if any(_suppression_matches(f, page_url, s, case_insensitive) for s in suppressions):
            continue
        out.append(f)
    return out


def _compile_patterns(patterns: list[str], case_insensitive: bool) -> list[re.Pattern[str]]:
    """Compile regex patterns; use re.IGNORECASE when requested."""
    flags = re.IGNORECASE if case_insensitive else 0
    compiled = []
    for p in patterns:
        if not p:
            continue
        try:
            compiled.append(re.compile(p, flags))
        except re.error:
            continue
    return compiled


def _snippet_around(text: str, start: int, end: int, snippet_chars: int) -> str:
    """Extract a snippet of length ~snippet_chars around the match span."""
    if not text or snippet_chars <= 0:
        return ""
    half = snippet_chars // 2
    s = max(0, start - half)
    e = min(len(text), end + (snippet_chars - (end - s)))
    if e - s < len(text):
        e = min(len(text), s + snippet_chars)
    out = text[s:e]
    if s > 0:
        out = "…" + out
    if e < len(text):
        out = out + "…"
    return out


def _window_around(text: str, center: int, window_chars: int) -> str:
    """Return substring centered at position with given character window."""
    if not text or window_chars <= 0:
        return ""
    half = window_chars // 2
    s = max(0, center - half)
    e = min(len(text), s + window_chars)
    return text[s:e]


def _has_qualifier_in_text(
    text: str,
    qualifier_groups: list[str],
    qualifier_phrases: dict[str, list[str]],
    case_insensitive: bool,
) -> bool:
    """Return True if text contains at least one phrase from any of the given qualifier groups."""
    if not text or not qualifier_groups:
        return False
    flags = re.IGNORECASE if case_insensitive else 0
    for group_name in qualifier_groups:
        phrases = qualifier_phrases.get(group_name) or []
        for phrase in phrases:
            if not phrase:
                continue
            try:
                if re.search(re.escape(phrase), text, flags):
                    return True
            except Exception:
                pass
    return False


def run_rules(
    text: str,
    policy_path: Path,
    page_url: Optional[str] = None,
) -> list[Finding]:
    """
    Run all rules from policy on extracted text. Returns list of findings.
    Handles: patterns, proximity, conditional (required_qualifiers_any), trigger_patterns.
    When require_upgrade_context is true, only reports on Upgrade-related pages; if
    upgrade_context_window_chars is set, Upgrade must appear near each match.
    Suppressions in policy (false positives) are applied before returning.
    """
    policy = _load_policy(policy_path)
    config = _get_scan_config(policy)
    qualifier_phrases = _build_qualifier_phrases(policy)
    case_insensitive = config["case_insensitive"]
    snippet_chars = config["snippet_chars"]
    qualifier_window = config["qualifier_window_chars"]
    proximity_window = config["proximity_window_chars"]
    upgrade_near_window = config.get("upgrade_context_window_chars", 0) or 0

    require_upgrade = (policy.get("scan") or {}).get("require_upgrade_context", True)
    if require_upgrade and not _is_upgrade_related(text, policy, case_insensitive):
        return []

    findings: list[Finding] = []
    rules = policy.get("rules") or []
    page_url = page_url or ""

    def _add_finding(rule_id: str, taxonomy: str, severity: str, match_text: str, snippet: str, recommendation: str, match_start: int, match_end: int) -> None:
        if require_upgrade and upgrade_near_window > 0:
            center = (match_start + match_end) // 2
            if not _has_upgrade_near_position(text, center, upgrade_near_window, policy, case_insensitive):
                return
        findings.append(Finding(
            rule_id=rule_id,
            taxonomy=taxonomy,
            severity=severity,
            match_text=match_text,
            snippet=snippet,
            recommendation=recommendation,
        ))

    for rule in rules:
        rule_id = rule.get("id") or "UNKNOWN"
        taxonomy = rule.get("taxonomy") or ""
        severity = rule.get("severity") or "MEDIUM"
        recommendation = rule.get("recommendation") or ""

        # --- Pattern rules (simple regex) ---
        patterns = rule.get("patterns")
        if patterns:
            compiled = _compile_patterns(patterns, case_insensitive)
            for pat in compiled:
                for m in pat.finditer(text):
                    match_text = m.group(0)
                    snippet = _snippet_around(text, m.start(), m.end(), snippet_chars)
                    required_any = rule.get("required_qualifiers_any")
                    if required_any:
                        window_text = _window_around(text, (m.start() + m.end()) // 2, qualifier_window)
                        if _has_qualifier_in_text(window_text, required_any, qualifier_phrases, case_insensitive):
                            continue
                    _add_finding(rule_id, taxonomy, severity, match_text, snippet, recommendation, m.start(), m.end())

        # --- Proximity rules ---
        prox = rule.get("proximity")
        if prox and isinstance(prox, dict):
            anchor_patterns = prox.get("anchor_patterns") or []
            near_patterns = prox.get("near_patterns") or []
            window_chars = prox.get("window_chars") or proximity_window
            a_compiled = _compile_patterns(anchor_patterns, case_insensitive)
            n_compiled = _compile_patterns(near_patterns, case_insensitive)
            for a_pat in a_compiled:
                for a_m in a_pat.finditer(text):
                    window_text = _window_around(text, (a_m.start() + a_m.end()) // 2, window_chars)
                    for n_pat in n_compiled:
                        if n_pat.search(window_text):
                            match_text = a_m.group(0) + " ... " + (n_pat.search(window_text).group(0) if n_pat.search(window_text) else "")
                            snippet = _snippet_around(text, a_m.start(), a_m.end(), snippet_chars)
                            _add_finding(rule_id, taxonomy, severity, match_text, snippet, recommendation, a_m.start(), a_m.end())
                            break
                    else:
                        continue
                    break

        # --- Trigger_patterns rules ---
        trigger_patterns = rule.get("trigger_patterns")
        required_any = rule.get("required_qualifiers_any")
        if trigger_patterns and required_any:
            t_compiled = _compile_patterns(trigger_patterns, case_insensitive)
            for t_pat in t_compiled:
                for t_m in t_pat.finditer(text):
                    window_text = _window_around(text, (t_m.start() + t_m.end()) // 2, qualifier_window)
                    if _has_qualifier_in_text(window_text, required_any, qualifier_phrases, case_insensitive):
                        continue
                    match_text = t_m.group(0)
                    snippet = _snippet_around(text, t_m.start(), t_m.end(), snippet_chars)
                    _add_finding(rule_id, taxonomy, severity, match_text, snippet, recommendation, t_m.start(), t_m.end())

    return _apply_suppressions(findings, policy, page_url, case_insensitive)


def run_rules_on_fixture(
    html_path: Path,
    policy_path: Path,
    extract_fn: Optional[Any] = None,
) -> list[Finding]:
    """
    Load HTML from file, extract text, run rules. For tests (no network).
    extract_fn(text) not used; we use extract_main_text from HTML string.
    """
    from src.extract import extract_main_text
    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    text, _ = extract_main_text(html)
    return run_rules(text, policy_path)
