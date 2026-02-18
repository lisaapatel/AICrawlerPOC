"""
Unit tests for the rules engine using saved HTML fixtures.
No network calls; loads fixtures and asserts expected rule IDs from expected_findings.json.
"""

import json
from pathlib import Path

import pytest

# Project root (parent of tests/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
POLICY_PATH = PROJECT_ROOT / "policy.yml"
EXPECTED_FINDINGS_PATH = PROJECT_ROOT / "expected_findings.json"


def _load_expected_findings() -> dict[str, list[str]]:
    """Load expected_findings.json; keys are fixture filenames, values are list of rule_ids."""
    if not EXPECTED_FINDINGS_PATH.exists():
        return {}
    with open(EXPECTED_FINDINGS_PATH, encoding="utf-8") as f:
        return json.load(f)


def _get_fixture_html_paths() -> list[Path]:
    """Return paths to all .html files in fixtures dir."""
    if not FIXTURES_DIR.exists():
        return []
    return sorted(FIXTURES_DIR.glob("*.html"))


@pytest.fixture(scope="module")
def policy_path() -> Path:
    return POLICY_PATH


@pytest.fixture(scope="module")
def expected_findings() -> dict[str, list[str]]:
    return _load_expected_findings()


@pytest.mark.parametrize("html_path", _get_fixture_html_paths())
def test_fixture_findings_match_expected(
    html_path: Path,
    policy_path: Path,
    expected_findings: dict[str, list[str]],
) -> None:
    """
    For each fixture HTML, run the rules engine and assert that the set of
    rule_id findings matches the set in expected_findings.json for that file.
    """
    from src.rules import run_rules_on_fixture

    if not policy_path.exists():
        pytest.skip("policy.yml not found")

    findings = run_rules_on_fixture(html_path, policy_path)
    found_ids = sorted({f.rule_id for f in findings})
    expected = expected_findings.get(html_path.name, [])
    expected_sorted = sorted(expected)

    assert found_ids == expected_sorted, (
        f"Fixture {html_path.name}: expected rule IDs {expected_sorted}, got {found_ids}"
    )


def test_run_rules_returns_findings_for_sample1(policy_path: Path) -> None:
    """Sanity check: sample1.html yields at least one finding."""
    from src.rules import run_rules_on_fixture

    if not policy_path.exists():
        pytest.skip("policy.yml not found")

    sample1 = FIXTURES_DIR / "sample1.html"
    if not sample1.exists():
        pytest.skip("sample1.html not found")

    findings = run_rules_on_fixture(sample1, policy_path)
    assert len(findings) >= 1
    assert any(f.rule_id == "ROLE_001_UPGRADE_IS_BANK" for f in findings)
    assert any(f.rule_id == "MKT_001_GUARANTEED_APPROVAL" for f in findings)


def test_run_rules_empty_text(policy_path: Path) -> None:
    """Empty text yields no findings from pattern/proximity rules."""
    from src.rules import run_rules

    if not policy_path.exists():
        pytest.skip("policy.yml not found")

    findings = run_rules("", policy_path)
    assert findings == []
