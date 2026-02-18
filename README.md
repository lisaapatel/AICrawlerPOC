# partner-portrayal-scanner

**POC for a feature test:** built this as a test before writing my PRD.

A compliance crawler for disclosures: scan partner pages for risky or misleading wording (e.g. CFPB/UDAAP-style) and get a CSV + HTML report with evidence.

---

## 3 things I learned

1. **Policy-in-YAML works.** Rules, qualifiers, and suppressions in one file—tune detection without touching code.
2. **Brand context has to be near the match.** If you only check “mentioned somewhere on the page,” you flag other parties’ copy. Requiring the brand within N characters of the match cuts false positives.
3. **You need a way to lock in false positives.** Mark findings, write them into policy (suppressions), re-run—signal stays useful.

---

## What we did

Scan URLs → extract text → run rules from `policy.yml` → `report.csv` + `report.html` + `evidence/`. Context gate (brand near match) and suppressions in policy; `mark_false_positives.py` to append from a marks CSV.

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scan.py --urls urls.txt --policy policy.yml
```

Open `report.html`. Screenshots: install Playwright, run with `--render js`.
