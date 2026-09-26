# 0007: Learn score weights on 2022-23 exclusions, test on 2024 onward

**Status:** Accepted. Refines [0004](0004-unsupervised-score-validated-on-leie.md).

## Context

The first real run scored prescribers with an equal-weight average of nine
peer-adjusted z-scores and evaluated it on every exclusion from 2022 to the
LEIE snapshot. Top-1% lift was 2.6x (15 of 572). The per-feature breakdown from
that run showed the metrics are far from equally informative, so equal weights
leave signal on the table. But re-weighting by looking at those same
exclusions and reporting the lift on them would inflate the result.

## Decision

Split the exclusions by date and keep the two roles apart:

- **Development** (first exclusion in 2022-2023): fit an L2-penalised logistic
  regression of exclusion on the clipped peer-adjusted z-scores, with
  non-negative slopes, and choose between the equal-weight and learned-weight
  scores by development average precision.
- **Test** (first exclusion from 1 Jan 2024 to 31 Jul 2026): measure the
  headline once, with a bootstrap CI, next to the equal-weight and unadjusted
  baselines. Prescribers excluded in the development window are dropped.
- **Pinned window end** (dbt var `outcome_window_end`). A fixed end date means
  loading a newer LEIE file cannot silently change the result.

The candidate set is generic: every feature goes into the regression and no
feature is dropped by hand. The per-feature results seen in the first run can
therefore not leak into the weights; only the 2022-2023 outcomes shape them.

## Result (2021 data, September 2026 LEIE snapshot)

161 development and 389 test exclusions. The learned-weight score was
selected on development and reached a test-window top-1% lift of 4.1x
(16 of 389; 95% CI 2.4-6.2x), against 2.6x for equal weights and 1.5x
without peer adjustment. The advantage is concentrated at the top: at 5-10%
the three scores are similar.

The test window first ran to the snapshot's last exclusion (20 Sep 2026) and
was then pinned to 31 Jul 2026. That change was made after seeing the first
result, so both are recorded: through September the lift was 4.1x
(17 of 411; 95% CI 2.3-6.3x), equal weights 2.4x, unadjusted 1.5x. The
conclusion does not depend on the choice.

## Consequences

- The headline now comes from a genuine out-of-time test, the standard way to
  validate a risk model.
- Being honest about sequence: the decision to try learned weights was made
  after seeing the first full-window evaluation. The protection is that the
  weights and the model choice use only development outcomes.
- With about 160 development events the weights are noisy. Some features that
  were informative in the test window (e.g. opioid claim share alone) got
  little weight because they showed nothing in 2022-2023. That is reported,
  not corrected.
