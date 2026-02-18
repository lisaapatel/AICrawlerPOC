# Partner Portrayal Scanner — PM Summary (What We Built, What Worked, What Didn’t)

**Plain English for PM / handoff to devs. No code.**

---

## What this tool does

We built a **local MVP** that:

- Takes a list of partner webpage URLs (e.g. PODS, rFinance, 1&Fund).
- Fetches each page, pulls out the main text, and runs a **rules engine** against your policy (in a YAML file).
- Flags risky or misleading wording about Upgrade / the loan offer (CFPB/UDAAP-style risk).
- Writes a **CSV report** and an **HTML report** with findings, plus **evidence** (saved HTML, extracted text, and optional screenshots).

**Goal:** PM demo and spec validation for compliance monitoring — *not* a legal determination.

---

## What we actually built (deliverables)

| Thing | What it is (plain English) |
|-------|-----------------------------|
| **scan.py** | The main script. You run it from the command line; it reads urls.txt and policy.yml, crawls the URLs, runs the rules, and writes the reports. |
| **policy.yml** | One file that holds all the rules: “flag this phrase,” “flag if X appears near Y,” “flag if they say APR but don’t say rates vary,” etc. Your team can edit this without touching code. |
| **urls.txt** | Simple list of partner URLs to scan (one per line). We put in PODS, rFinance, and 1&Fund seed URLs. |
| **report.csv** | Spreadsheet: one row per finding, with URL, rule that fired, severity, snippet of text, recommendation, page link, and screenshot path (if you ran with screenshots). |
| **report.html** | Web page you open in a browser: same findings, grouped by URL, with the **page link** and (when screenshots are on) a **screenshot** of the page. |
| **evidence folder** | Saved copies of each page: raw HTML, extracted text, and a small JSON with title/URL/status. Optional: full-page screenshots when you use “JS rendering.” |
| **Upgrade-context gate** | A setting so we **only report findings when the page actually mentions Upgrade** (or a variant like “Upgrade, Inc.”). Stops us from flagging other lenders’ disclosure text (e.g. Citi on PODS) when it’s not about Upgrade. |
| **Tests** | Automated checks that run the rules on saved example HTML files and compare to an expected list of rule IDs. No live web calls in tests. |

---

## What worked

1. **End-to-end flow**  
   Run one command → URLs get fetched → text is extracted → rules run → CSV + HTML + evidence are written. It runs and produces usable output.

2. **Policy-driven rules**  
   All rule logic lives in **policy.yml**. You can add/change rules (patterns, “X near Y,” “must have qualifier,” “trigger + qualifier”) and rerun without code changes.

3. **Reports are usable**  
   - **CSV** is good for sharing with compliance, filtering, and counting.  
   - **HTML** is good for viewing in a browser: you see the **page link** and (when enabled) a **screenshot** next to each finding.

4. **Upgrade-context filter**  
   Once we added “only report when the page mentions Upgrade,” we stopped getting findings for content that was clearly about other lenders (e.g. Citi on PODS). That’s the right behavior for “partner portrayal of *Upgrade*.”

5. **Polite crawling**  
   We use a clear user-agent, timeouts, one retry, and a short pause between requests so we don’t hammer partner sites.

6. **Evidence is saved**  
   You have raw HTML, extracted text, and meta for every URL. That’s enough to debug why a rule fired and to show “this is what we saw on the page.”

7. **Tests**  
   The test harness runs the rules on fixed HTML and checks that the right rule IDs appear. That gives you a safety net when you change policy or code.

---

## What didn’t work or was limited

1. **Screenshots**  
   - We added **screenshot capture** and **page link** to the report (CSV + HTML).  
   - Screenshots only work when you run with **“JS rendering”** (Playwright).  
   - In your environment, Playwright wasn’t installed in the virtual environment, so the run fell back to plain HTTP and **no screenshots were saved**.  
   - **Bottom line:** The feature is implemented; your devs need to install Playwright and run with `--render js` to get screenshots. Until then, you still get the **page link** for every finding.

2. **PODS still had 4 findings**  
   - Those were all “APR mentioned without qualifier nearby” (DISC_001).  
   - The page *does* mention “Upgrade” somewhere (e.g. financing powered by Upgrade), so the whole page is treated as “Upgrade-related” and we run all rules.  
   - The actual APR text is about **Citi**, not Upgrade. So we’re still flagging **context that isn’t really about Upgrade’s offer**.  
   - **For a polished version:** You’ll want “Upgrade context” to be **near the match** (e.g. “Upgrade” within N characters of the flagged text), not just “somewhere on the page.” That would require a small rule-engine change.

3. **No web UI**  
   - Everything is command-line. You run a script, then open report.html in a browser.  
   - We did *not* build a “leave the crawler open in the browser” web app (dashboard, “Run scan” button, etc.). That would be a separate, small project for your devs.

4. **No database**  
   - By design: output is files only (CSV, HTML, evidence folder).  
   - For a polished product you’ll likely want a DB to store runs, track findings over time, and support workflows (e.g. “acknowledged,” “fixed,” “re-scan”).

5. **Single run at a time**  
   - The tool runs once per invocation. There’s no scheduling (e.g. “scan these URLs every week”) or queue. That would live in a polished system (cron, task queue, or SaaS).

---

## What you have today (files and commands)

- **Project folder:** `partner-portrayal-scanner/`  
- **Config:** `policy.yml` (rules, `scan.upgrade_context_window_chars`, `suppressions`), `urls.txt`, optional `expected_findings.json`.  
- **Run scan (no JS):**  
  `python scan.py --urls urls.txt --policy policy.yml`  
- **Run scan with JS + screenshots:**  
  `python scan.py --urls urls.txt --policy policy.yml --render js`  
  (Requires Playwright installed.)  
- **Mark false positives and append to policy:**  
  Edit `false_positive_marks.csv` (columns: url, rule_id, snippet_contains, match_contains, url_contains, reason), then:  
  `python mark_false_positives.py --marks false_positive_marks.csv --append-policy`  
  Re-run the scan to see fewer false positives.  
- **Run tests:**  
  `pytest tests/ -v`  
- **View results:**  
  Open `report.html` in a browser; use `report.csv` for spreadsheets. Evidence is under `evidence/`.

---

## Things to think about for a polished version (for your developers)

1. **Upgrade context near the match**  
   Right now “Upgrade-related” means “the page mentions Upgrade somewhere.” For a better signal, require “Upgrade” (or a variant) to appear **within X characters of the flagged text**. That way you don’t flag Citi’s APR when the only Upgrade mention is in the footer.

2. **Screenshots as a first-class feature**  
   Decide whether every scan should capture screenshots (and depend on Playwright) or only when requested. Document the install (Playwright + browser) and consider a fallback message in the UI when screenshots aren’t available.

3. **Web UI / “crawler open in web”**  
   If you want people to “leave the crawler open in the browser,” you need a small web app: dashboard, “Run scan” (or “Scan these URLs”), and “View latest report.” That implies a backend (even a simple one) and serving the report + evidence from the same place.

5. **Storing runs and history**  
   A polished product usually has: run ID, timestamp, list of URLs, list of findings, and maybe status per finding (e.g. “open,” “acknowledged,” “fixed”). That suggests a database and possibly an API for the front end.

6. **Scheduling and re-scanning**  
   You may want “scan these partner URLs every week” or “re-scan when we add a new URL.” That’s either cron + this script or a proper job queue in your stack.

7. **Permissions and security**  
   If the tool is used by more than one person or team: who can run scans, who can change policy, and where reports/evidence are stored (and who can see them). Think auth and access control for the polished version.

8. **Policy management**  
   Right now policy is a YAML file in the repo. In a product you might want: versioned policy, approval workflow, or a UI for compliance to enable/disable rules or adjust wording without editing YAML.

9. **Alerting and workflows**  
   Do you want email/Slack when new HIGH findings appear? Or a simple “findings inbox” in the UI with assign and resolve? That shapes what the backend and UI need to do.

10. **Scale and performance**  
   For many URLs or large pages, you might need rate limiting, timeouts, and maybe parallel workers. The current MVP is single-threaded and polite; your devs can tune that when they own the codebase.

11. **Legal and compliance**  
    Keep the disclaimer clear: this is for **monitoring and PM/compliance workflow**, not a substitute for legal review. The polished version should state that in the UI and in any export (e.g. in the report footer).

---

## One-line summary

**We built a working local MVP that scans partner URLs with a policy-driven rules engine, writes CSV + HTML reports with page links (and optional screenshots), and only flags pages that mention Upgrade; screenshots need Playwright installed, and a polished product would add a web UI, run history, and “Upgrade context near the match” so you don’t flag other lenders’ text.**

You can hand this summary and the repo to your developers as the spec and “what’s done / what’s next” list.
