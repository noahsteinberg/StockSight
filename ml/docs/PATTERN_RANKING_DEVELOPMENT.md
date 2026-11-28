# Historical-pattern ranking diagnostic

## Result

The approved bounded diagnostic does not justify releasing model recommendations.
It used 26,211 matched stock/date observations, 98.23% of the 26,682 observations
with sufficient history and a resolved 21-session outcome. The development
reader contained 474 stocks and yielded 58 monthly cutoffs from January 2014
through October 2018. November and December lacked a complete 21-session
outcome inside the development boundary. No observation from 2019 onward was
loaded or scored.

| Method | Mean within-date rank correlation | Gross top-minus-bottom decile spread | Top-decile turnover |
| --- | --- | --- | --- |
| Historical-pattern median | 0.02286 | 0.25494 percentage points | 75.05% |
| 20-session momentum | -0.03379 | -0.34594 percentage points | 88.08% |
| Prior historical median | 0.01780 | 0.29450 percentage points | 6.96% |

The pattern method has a weak positive ranking association. Its spread is below
the prior-median baseline, and a fixed illustrative 40-basis-point roundtrip
long-short charge reduces it to -0.14506 percentage points. This charge assumes
10 basis points each way on each of two legs. It is a sensitivity check, with
no claim about actual liquidity, costs or execution.

Annual pattern rank correlations were -0.01181, 0.03785, 0.03000, 0.03828 and
0.01943 for 2014 through 2018. The mean distance across chosen matches was
0.31784 in standardized feature units. These numbers provide no calibrated
probability and establish no useful similarity cutoff.

## Fixed method

Read the existing frozen Parquet with a pushed-down December 31, 2018 cutoff.
Apply the application's existing bar validation and six-decimal price
representation. Use each month's last observed universe session. Evaluate
only stocks observed on that date with at least 100 prior stored observations
and a resolved 21-session outcome within development.

For each stock/date, reproduce the app's three-feature nearest-period retrieval
over up to 2,500 trailing sessions, using only candidate outcomes complete by
the cutoff. Use up to 12 non-overlapping paths and require eight. Fit feature
scales only to eligible setups at that date. The ranking score is the median
matched 21-session price change. Six direct parity checks against the
application calculation passed for score and average match distance.

Compare all three methods on the same eligible stock/date rows. The prior
median uses all eligible historical 21-session candidate outcomes at that
cutoff, without nearest-period selection. Momentum uses the trailing 20-session
price change. Compute Spearman correlation within each date and average dates
equally. The extreme groups contain the ceiling of 10% of eligible stocks,
with ticker as a deterministic tie-break. Turnover is one minus the overlap
with the prior top group divided by the larger group size.

## Limits and next action

- The snapshot universe has survivorship bias and unverified price adjustment.
  Returns are price-only, excluding dividends.
- Recorded corporate-action outcome windows are excluded. Coverage is
  conditional on that cleaning. Missing observations count as stored sessions.
- Monthly 21-session outcomes can overlap. Observations and matched examples
  are dependent. These descriptive averages carry no independence-based
  confidence interval.
- Outcomes use the cutoff close, so this does not establish executable
  next-entry performance or publication timing.
- The development period has been reused. Protected validation and the final
  test remain reserved.

Retain historical patterns as inspectable educational evidence. Ship Research
ideas based on explicit observed momentum/variability metrics. Any forecasting
follow-up needs a newly approved protocol addressing the universe, execution
timing, costs and uncertainty before protected evaluation. No model was
trained, exported or promoted by this diagnostic.

## Reproduce

From backend in the existing import/refresh research environment, run
`python -m app.evaluate_patterns /private/path/prices_clean.parquet /new/output.json`.
The output path must be new. The reader rejects duplicate/out-of-order
ticker/date keys, checks the source hash before and after, and saves aggregate
metrics only.

[Aggregate report and environment](../reports/pattern_ranking_development_v1.json)
records the source hash, coverage, per-year and per-date metrics.
