# Historical Pattern Explorer

## Current approved behavior

Patterns now live in an expandable section below Analysis's chart. Use
`/#/analysis?symbol=AAPL&horizon=21&patterns=1` to open it, or expand
Historical patterns manually. A missing horizon defaults to 21. Old
`/#/predictions?symbol=AAPL&horizon=5` links redirect to the corresponding
Analysis section. Model status remains accessible from Analysis's research
signal link. The earlier Predictions-only flow below records Parth's original
PR checkpoint.

The match table now returns `match_distance`, the Euclidean distance over the
active standardized features. Smaller numbers mean closer setups, with no
validated useful cutoff. The frontend accepts older responses without this
field and displays Unavailable for distance.

An unavailable `current_event_window` identifies recorded split/distribution
events crossing the current 50-session setup. Short history and insufficient
non-overlapping matches have separate explanations. The 21-session empty state
offers an explicit 5-session switch. Requirements remain eight usable examples
and at most 2,500 stored calculation sessions.

The bounded ranking experiment is documented in
[the development diagnostic](../ml/docs/PATTERN_RANKING_DEVELOPMENT.md). It does
not qualify a serving model.

## Original PR checkpoint

Parth approved this increment on November 27, 2026: put a historical-comparison
panel on Analysis and show a local working preview first. After reviewing it,
he authorized a feature-branch push and PR for Noah. Merge and deployment remain
unauthorized; Noah retains release review. Vercel only deploys main, with feature
branches disabled by the existing configuration.

## What it does, in simple language

- On Analysis, the bright **5 sessions** and **21 sessions** links open Predictions
  for that stock and window. Predictions loads the full explorer automatically
  and lets the user change stocks. This page flow was explicitly approved by
  Parth after his first local review; Compare is outside this follow-up.
- Looks for earlier periods when the selected stock's price movement looked
  similar to its latest stored setup.
- Shows what actually happened over the next 5 or 21 stored sessions in those
  examples. Users can inspect each date and highlight its path.
- Reports the median, middle half of outcomes and counts of rises, falls and
  unchanged prices. These describe the selected examples; they are not an
  estimated chance of profit or a validated prediction.
- Reads existing stored daily prices. It does not change Supabase, ingest
  provider data, train a model or replace the unavailable model signal.

## Version 1 calculation

`historical-price-patterns-v1` reads the latest 2,500 observations, oldest first.
A setup at index t uses only prices available through t:

1. 20-session change: `100 × (close[t] / close[t-20] - 1)`.
2. Daily variability: sample standard deviation (ddof 1) of the 20 daily
   percentage close changes ending at t.
3. Price vs. average: `100 × (close[t] / mean(close[t-49:t+1]) - 1)`.

Candidates need 50 stored observations for the setup and a fully observed
5- or 21-session later path by the query's `as_of` date. A candidate is excluded
if its entire setup-and-outcome window contains a recorded `stock_splits`
ratio other than zero or one, including ambiguous distributions. A recorded
event in the current 50-observation setup makes matching unavailable. Events
are excluded, not adjusted. Unrecorded actions may still distort comparisons.

Scale each feature by its sample standard deviation across eligible historical
setups. Omit constant dimensions (scale at most 1e-12). Rank by equal-weight
Euclidean distance to the latest setup, breaking ties by earlier index. The
selection function receives setup features and indices, never later returns.

Walk that ranking greedily, retaining at most 12 candidates whose outcome paths
share no observations, including endpoints (index distance must exceed the
horizon). Require at least eight matches; otherwise return unavailable. Flat
setups with no varying dimensions also return unavailable. Setup windows can
overlap and examples are not statistically independent. This greedy selection
does not claim to optimize the entire set of matches.

Each path starts at zero and uses `100 × (later close / setup close - 1)`.
Quartiles and median use linear interpolation at `(n-1) × q`, calculated
separately at every path step. Rise/fall/unchanged counts use the unrounded
ending change. These are price changes excluding dividends. The plot's median
line is a pointwise summary, not necessarily one actual example's path.

Stored-session counts do not guarantee consecutive exchange sessions: missing
observations stretch calendar durations. History is bounded by availability,
retention, selection and source adjustment limitations. It is not a random
sample or an out-of-sample forecasting evaluation. ML promotion remains
separate under the existing research gates.

## Storage and UI contracts

One joined SELECT reads the bounded prices and series metadata together, so
the calculation is tied to one committed snapshot. No schema changes or writes
are required. Fixture mode explicitly uses the existing Plotly AAPL history;
database failure never falls back to it.

The full explorer lives on Predictions. Its shareable route is
`/#/predictions?symbol=AAPL&horizon=5` (or 21). Missing or invalid horizons use
21. Both Analysis links and the navigation preserve the selected ticker; the
on-page horizon buttons update the URL for reload/back/forward. Results load
automatically after a lightweight recent-price snapshot check. The existing
unavailable ML status is separate, in an expandable section.

The frontend validates identity, horizon, dates, counts, non-overlapping paths,
endpoints and all summary quartiles before display. The response must match
the independent price response's snapshot ID and `as_of`; otherwise results are hidden and a joint
refresh is offered. Changing ticker unmounts the panel. Changing horizon cancels
and keys requests so an older response cannot overwrite the new choice.
Timeout is 10 seconds, with retry. Analysis entry links hide during historical
replay. Changing the visible chart range does not change the calculation history.

## Local review evidence — November 27

- Full hosted-data catalog acceptance through the local feature API: all 494
  supported stocks passed both horizons (988/988 available responses, zero
  unavailable states and zero errors). Every response passed the frontend's
  path/summary validation and agreed with its chart snapshot and cutoff date.
  This is catalog/API evidence, not 494 separate browser walkthroughs or
  evidence of prediction accuracy. Future corporate actions or short histories
  can still correctly produce an unavailable state.
- Backend: 207 passed, 3 skipped; includes 17 new numerical, fixture HTTP and
  migrated SQLite tests. Ruff lint and format checks passed. PostgreSQL-specific
  tests were not run against a disposable PostgreSQL instance.
- Frontend: three Node contract tests passed, including multiple invalid-response
  cases. ESLint and production build passed. The existing large-bundle warning
  remains.
- Browser: local preview with actual stored data checked both horizons, example
  expansion, keyboard selection, highlighted path and replay hiding. At 320 px,
  the document stayed 320 px wide and example-table overflow stayed local.
- The new Playwright suite is checked in but could not run here: the required
  Chromium headless executable is missing. It stopped on the first launch;
  these are not reported as passing automated browser tests.
- Review URL while local servers run:
  `http://127.0.0.1:5188/#/predictions?symbol=AAPL&horizon=5`.

The original PR head subsequently passed GitHub CI: 280 backend tests, 75 public
browser cases and 30 account browser cases. The approved page-flow update has
five local Node contract/navigation tests, lint and build passing; its browser
coverage is checked through the updated PR CI. The numerical API has not changed,
so the 494-stock acceptance above remains evidence for the same calculation.

## Repeat the checks

From `frontend`, run `npm run test:unit`; CI also runs these response-contract
tests. Run the normal lint/build and browser checks from LOCAL_START.md.

With the feature backend already running against the intended stored data,
run `node scripts/check-pattern-coverage.mjs http://127.0.0.1:8000 /private/tmp/pattern-coverage.json`.
Choose an output path outside Git. This is a read-only public-API check, with
three workers and a 10-second timeout matching the UI. It reads the supported
catalog, checks both horizons for every ticker using the frontend validator,
and verifies chart snapshot/date agreement. It reports valid unavailable states
separately from HTTP, timeout or contract failures. It never writes to the database.

Next: Noah reviews the focused feature PR. The separate ranking experiment was
not strong enough to approve a prediction model, so this panel intentionally
shows actual historical examples and their limits. Run the checked-in Playwright
suite in an environment with its pinned Chromium before release. Do not merge
or deploy this feature as part of the current task.
