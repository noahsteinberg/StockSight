# ADR-0003: adj_close as the price basis for returns and labels

**Date**: 2026-11-13
**Status**: proposed
**Deciders**: ML team (pending review), drafted with Claude Code

## Context

Yahoo provides `close` (split-adjusted only) and `adj_close` (split- and dividend-adjusted). On spin-offs and special dividends `close` shows fake crashes that shareholders never suffered (MO −70% in 2008, KDP −82% in 2018); `adj_close` mostly removes them (KDP becomes +11.5%). `adj_close` is back-adjusted: its *level* on a past date changes whenever a later dividend or split occurs. See [prediction contract](../../ml/docs/prediction-contract.md), sections 2 and 3.4.

## Decision

Returns and labels use close-to-close `adj_close`. Features may use only returns and ratios (scale-invariant), never price or volume levels, because back-adjusted levels encode future corporate actions.

## Alternatives Considered

### Alternative 1: `close` (split-adjusted only)
- **Pros**: Closer to the printed price; never rewritten for dividends.
- **Cons**: Spin-offs and special dividends become large fake drops in labels and features.
- **Why not**: Corrupts labels on exactly the days with the largest moves.

### Alternative 2: Rebuild point-in-time unadjusted prices from splits and dividends
- **Pros**: True as-of prices; no back-adjustment.
- **Cons**: Extra code and still needs adjustment for return continuity.
- **Why not**: Ratio-only features give the same leakage protection with far less work.

## Consequences

### Positive
- Labels reflect total return, which is what a holder experiences.
- The ratio-only rule makes the back-adjustment harmless.

### Negative
- Features like "price above $100" or raw volume are not allowed.
- Labels change slightly if Yahoo later revises its adjustment; snapshots must be recorded.

### Risks
- A level-based feature slipping in. Mitigation: tests and `mle-reviewer` check feature definitions against this rule.
