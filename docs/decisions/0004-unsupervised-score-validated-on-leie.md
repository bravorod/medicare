# 0004: Unsupervised peer-adjusted score, validated on later LEIE exclusions

**Status:** Accepted; weighting and evaluation refined by [0007](0007-temporal-holdout-for-the-score.md)

## Context

We want a score that flags prescribers for review. LEIE exclusions are the
only public, prescriber-level outcome. They are rare (a fraction of a percent
of prescribers over several years) and have many causes.

## Options considered

- **Supervised classifier on LEIE.** With few positives it overfits easily,
  the definition of risk becomes opaque, and it learns whatever correlates with
  exclusion (including non-prescribing causes).
- **Isolation forest / other black-box anomaly detection.** It does not respect
  peer groups naturally and is hard to explain feature by feature.
- **Regression-based peer adjustment + robust z composite** (chosen).

## Decision

For each metric, regress out peer-group fixed effects and beneficiary case-mix,
convert residuals to robust z-scores, and average the positive parts with
equal weights. **The exclusion outcome is never an input.** It is used only to
evaluate lift at the top 1% (and 0.1%-20%) with a bootstrap CI, against an
unadjusted baseline and single-feature baselines.

## Consequences

- Every flag can be explained ("cost per fill 5 robust SDs above same-specialty
  peers in the same state, after adjusting for patient risk").
- Equal weights are a deliberate prior, not a tuned choice. Tuning the weights
  on LEIE would turn the validation into training and inflate the lift.
- Lift at 1% rests on a modest number of events. The CI is reported every time
  the point estimate is.
