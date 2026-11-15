# Phase 1 adversarial review

Reviewed November 15, 2026. Review status: complete for source/API/tooling checks; rendered UI verification remains incomplete.

## Scope and provenance

- Repository: noahsteinberg/StockSight.
- Head: e71db4fe738d7c6aac103135b9ea857df6df48eb, feature/frontend-redesign.
- Base: 89fa1c8fa57aacef60cfd30e506ca0147226ea83, locally available origin/main.
- GitHub open-PR search returned no results. This is a branch review, not a posted PR review. The remote base was not freshly fetched, so conclusions apply to these exact revisions rather than unseen subsequent changes.
- Reviewed all 16 changed file paths: routing, API/data adapter, fixture/license, tests, frontend request/state/rendering, styles, metadata, ignore exception, setup/API/architecture/roadmap documentation. Existing report files were preserved.
- Code execution used an isolated clone named stocksight-phase1-review. No production source changes or dependency upgrades were made during this review.

## Verified evidence

| Check | Outcome |
| --- | --- |
| Fresh npm ci in isolated checkout | Succeeded; temporary tarball retry warnings occurred, final install exited successfully |
| Frontend npm run lint | Passed |
| Frontend npm run build | Passed, 17 modules transformed |
| Existing backend pytest suite | Four tests passed |
| Backend Ruff lint | Passed before adding review-only probes |
| Backend Ruff format check | Eight repository files already formatted |
| Expanded adversarial API suite | 28 tests passed: four repository tests plus 24 review-only cases |
| Full npm audit | Three moderate package entries, all connected to the same minimatch advisory |
| npm audit --omit=dev | Zero reported vulnerabilities at review time |
| Lockfile comparison with base | No changes; the flagged tooling dependency predates Phase 1 |

Python execution used an existing isolated Python 3.12.14 environment with the project's dependencies; it was not a fresh Python installation and does not prove Linux/Python 3.13 CI compatibility. Frontend installation was fresh. No hosted CI execution is claimed.

The 24 additional cases verify all four range sizes (21/63/252/506), retained latest observation date, finite OHLCV values, OHLC bounds, case/space normalization, symbol/name matching, invalid ranges including a long value, unsupported/injection-like/Unicode symbols, correct 404/405 boundaries, OpenAPI availability, service-name injection, default range, and repeatable results.

All 506 observations were exercised through the all-history response. Last observation: 2017-02-16. Fixture SHA256 in this review checkout: 04053FD4AB339DD81A2BD14153E4BE4FD88AE209FBC7ACA29BC1096A3CBE7F27. This identifies the reviewed file; it does not independently verify the upstream market observations or data redistribution rights.

## Confirmed Phase 1 finding

### P3: Whitespace-only ticker submission silently does nothing

Location: frontend/src/Analysis.jsx:43–45. The native required input rejects the empty string, but accepts a nonempty string of spaces. The handler trims that value and immediately returns when it becomes empty, without setting an error or reporting invalidity.

Trigger: replace AAPL with spaces and submit Search. By source tracing, no fetch, state change, or user feedback occurs. A required-looking input can therefore fail silently. The Luna max reviewer independently identified this path. It was not dynamically reproduced in a rendered browser during this review, so the finding is source-confirmed rather than a claimed browser observation.

Impact: a minor validation/usability defect; it does not corrupt data or expose private information. Recommendation: reject whitespace with an accessible concise message or native custom validity, clear validity as the user edits, and cover this interaction in the browser test suite. No production fix was applied under the review-only scope.

## Confirmed dependency finding

### P2 maintenance: development-tool dependency has a moderate advisory

Location: frontend/package-lock.json:1885 (minimatch package entry); ESLint dependency references at lines 343 and 1155. Installed version: minimatch 10.2.6.

Evidence: npm audit reports GHSA-g3hv-75wg-m249 and propagates it through ESLint and @eslint/config-array. These are three package entries for one underlying advisory, not three independently demonstrated application exploits. The upstream advisory describes excessive CPU/memory use when an attacker controls particular glob patterns with the relevant optimization setting. Source: https://github.com/advisories/GHSA-g3hv-75wg-m249.

Impact: potential development/CI tooling denial of service under the advisory's trigger conditions. No route from a stock ticker request to minimatch was found; production-only npm audit returned zero. No exploit was run. This lockfile is unchanged from base, so this is a pre-existing maintenance issue, not a Phase 1 regression.

Recommendation: prepare a focused compatible ESLint/dependency update, inspect the lockfile changes, and rerun lint/build/audit. Do not blindly force a major-version override or claim production exposure from the audit count alone.

## What source tracing supports, without claiming browser execution

- Each effect creates an AbortController and ten-second timeout; cleanup disables stale updates and aborts the old request. The active flag is checked before updating result state. This is a plausible race defense, not dynamic proof of every timing case.
- Search and retry increment a request counter, allowing the same symbol to be submitted again. Changing the selected range clears prior data and selection before issuing the new request.
- Unknown symbols return a structured 404; invalid ranges use FastAPI validation. The UI handles non-OK responses before rendering and includes loading, empty, error, and retry paths.
- The committed source controls the fixture and response URL. A malformed replacement dataset or future mismatched API payload was not treated as a current user-triggerable bug. Add response/fixture validation when broadening the data boundary.
- API output is chronological and range filtering retains the latest records, avoiding the earlier project's oldest-record LIMIT issue.
- The app explicitly labels the data historical. M2 database/ingestion, accounts, indicators, and ML are out of Phase 1 scope and are not defects in this slice.

## Verification gaps and release decision

The roadmap's complete M1 gate is not established by passing API tests and build checks. Required remaining evidence includes repeatable browser checks for timeout, API-down/retry recovery, rapid search/range changes, date-slider behavior, empty data, narrow layouts, and setup on another teammate's machine. Automated browser tests are not committed in the reviewed revision. Earlier browser observations from the implementation session are not substituted for this independent review.

The adversarial-review skill requests a Luna max reviewer using an isolated headless browser. A Luna max reviewer independently inspected the Phase 1 UI source. It reported Playwright/Puppeteer unavailable and unsuccessful isolated browser attempts, so no actual rendered UI result or screenshot was verified. No live-user browser session was substituted as review evidence. Treat mobile layout, actual timeout/retry recovery, and accessibility announcements as unverified.

Recommendation: the historical API slice passes the exercised checks, with no reproduced blocking API regression. The source-confirmed whitespace issue is low severity. Address it in the next validation patch and plan a focused development-tool dependency update. Do not label the entire M1 milestone complete or call the change unconditionally safe to merge until material browser verification gaps are resolved. A documented development demo and a professor-ready release are different completion levels.

## Reproduce the API probes

The review cases are preserved in docs/reviews/phase1_api_probes.py. From backend, after installing requirements-dev.txt in a virtual environment:

    python -m pytest
    python -m pytest ../docs/reviews/phase1_api_probes.py
    python -m ruff check .
    python -m ruff format --check .

From frontend:

    npm ci
    npm run lint
    npm run build
    npm audit --json
    npm audit --omit=dev --json

The expanded run used the same cases temporarily placed under backend/tests in the isolated checkout. One initial review invocation used an incorrect pythonpath override from the repository root and failed collection; rerunning from the documented backend directory passed all 28 tests. This was a review harness mistake, not a repository defect. A restricted audit DNS failure was rerun with network permission before recording the successful result.

## Change log for this review

Added this report and the reproducible API probe artifact only. Did not modify application code, change dependencies, merge branches, post a GitHub review, or push the report. Prior local reports remain untouched. Noah and Gavin continue to jointly own frontend/backend integration; the independent checks do not claim Noah's approval or second-machine verification.

## Recommended next work

1. Fix whitespace validation in a small patch and test it alongside unsupported ticker recovery.
2. Add automated browser tests for real API happy paths plus controlled error, timeout, empty-response, and rapid-request cases; cover keyboard date inspection and a narrow viewport.
3. Update the development dependency chain in a separate patch and rerun lint/build/audit.
4. Repeat launch from the documented commands in a clean environment or second machine before marking M1 complete. Gavin and Noah jointly own the integration contract; verification can continue without waiting for synchronous teammate availability.

## Rendered UI verification retry November 15, 2026

The user requested another UI verification attempt after the independent review. A new temporary in-app browser tab successfully accessed the existing running development frontend and FastAPI. This was direct rendered testing in a separate tab, not the previously unavailable isolated headless/Luna setup. It resolves the specific manual checks below but does not establish automated browser coverage or second-machine setup.

Observed results:

- Initial 3M view: 63 sessions, ending 2017-02-16; latest close $135.35 and volume 22,118,000.
- 1M: 21 sessions, 2017-01-19 through 2017-02-16.
- Keyboard Home on the date slider: selected the first 1M observation, displaying 2017-01-19, $119.78, volume 25,597,300.
- 1Y: 252 sessions; changing range reset selection to the latest record.
- All: 506 sessions, beginning 2015-02-17 and ending 2017-02-16.
- MSFT submission: displayed unsupported-symbol message. Submitting space-padded lowercase aapl recovered the chart.
- Whitespace-only submission: reproduced the P3 finding in the actual rendered page; no validation message appeared and the previous chart remained.
- Stopped the API process started for this demo, submitted AAPL, and observed a controlled API-unavailable message plus Retry. Restarted the same backend, clicked Retry, and observed successful chart recovery. API was left running.
- At 390x844, search/range controls and date inspection remained visible without apparent horizontal layout overflow in the inspected viewport. The chart's axis labels were too small to read comfortably.
- Expanded Price observations: Date, Close (USD), and Volume columns appeared with the expected 21 records and matching first/latest values.
- Restored the browser viewport and closed the temporary verification tab; the user's original tab was preserved.

### Additional P2 usability finding: chart tick labels shrink excessively on narrow screens

Locations: frontend/src/Analysis.jsx:56–60 and frontend/src/styles.css (.price-plot and .price-plot text). The chart uses a fixed 980-unit viewBox with 11-unit tick text, scaled to the available width. At a 390px viewport, the actual plot width is roughly 350px, shrinking those labels to approximately four CSS pixels. The rendered screenshot confirmed hard-to-read axes. The observations table remains a useful alternative, but does not make the visual axes legible.

Recommendation: use responsive chart dimensions/tick typography or position readable labels outside the scaled SVG; reduce tick density on narrow layouts if necessary. Verify price and date labels at 390px before marking the responsive chart complete. No UI code was changed during this verification retry.

Remaining checks: automated browser coverage, controlled ten-second timeout, rapid-request races, synthetic empty-response rendering, and fresh setup on another machine. The successful API-down/Retry check above supersedes the earlier manual-recovery gap for the running local environment only.
