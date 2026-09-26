# 0003: Indirect standardization for the brand gap, regression as a check

**Status:** Accepted

## Context

Brand-name share differs a lot by specialty (endocrinology vs. family
practice) and by state, and industry payments are concentrated in
high-brand specialties. A raw paid-vs-unpaid comparison would mostly measure
specialty mix.

## Options considered

1. **Crude difference in brand share.** Confounded by specialty. Reported for
   transparency only.
2. **Indirect standardization.** Expected brand fills come from unpaid peers
   in the same specialty and state, and the O/E ratio is compared. It is
   transparent, runs in SQL, is easy to explain, and weights by volume.
3. **Regression with fixed effects.** Adds case-mix controls and gives CIs, but
   is harder to explain to non-technical readers.
4. **Propensity matching.** Needs choices about the matching model and discards
   data, and adds little over (2)+(3) here.

## Decision

Use (2) as the headline because it can be computed and explained in SQL. Use
(3), a Poisson GLM with the peer expectation as offset, case-mix controls and
peer-clustered SEs, as the robustness check. Report both, plus the crude gap.

## Consequences

If (2) and (3) disagree materially, the memo must say so. Neither addresses
selection (manufacturers targeting high prescribers). The drug-matched
analysis gives a sharper, but still observational, view.
