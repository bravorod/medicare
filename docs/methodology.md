# Methodology

This document defines every number the project reports. The SQL lives in
`dbt/models`, the modelling code in `src/partd_risk`, and each section names
both.

- [1. Data and cohort](#1-data-and-cohort)
- [2. Brand vs. generic classification](#2-brand-vs-generic-classification)
- [3. Industry payments and brand-name prescribing](#3-industry-payments-and-brand-name-prescribing)
- [4. Generic-substitution savings](#4-generic-substitution-savings)
- [5. Peer-adjusted outlier score](#5-peer-adjusted-outlier-score)
- [6. Validation against later OIG exclusions](#6-validation-against-later-oig-exclusions)
- [7. Robustness checks](#7-robustness-checks)

---

## 1. Data and cohort

| Source | Year | Grain | Used for |
|---|---|---|---|
| Medicare Part D Prescribers - by Provider and Drug | 2021 | NPI x brand x generic | brand/generic fills, drug-level costs |
| Medicare Part D Prescribers - by Provider | 2021 | NPI | totals, opioid measures, beneficiary case-mix |
| Open Payments General Payments | program year 2021 | payment | industry payments by NPI |
| OIG List of Excluded Individuals/Entities (LEIE) | snapshot at download | exclusion | outcome for validating the score |
| NPPES NPI registry | snapshot at download | NPI | entity type, taxonomy, practice location |

**Why 2021.** 2021 is the first Open Payments program year that publishes the
recipient NPI directly (earlier years need a fuzzy name/address match), and it
leaves a follow-up window of several years for later exclusions.

**Cohort** (`int_prescribers__cohort`). A prescriber is analysed when they:

1. are an individual (Part D entity code `I`, or NPPES entity type 1 when the
   Part D code is missing);
2. have a specialty and a state;
3. have at least `min_total_fills` (default 100) 30-day fills in the drug-level
   file, which keeps brand shares from being dominated by noise;
4. were **not** already on the OIG exclusion list by 31 Dec 2021.

`rpt_cohort_flow` reports how many prescribers each rule removes.

**Peer groups.** Specialty x state when that cell has at least
`min_peer_group_size` (default 25) cohort members; otherwise the specialty
nationally; otherwise all prescribers. The peer group is stored on every row
(`peer_group_id`, `peer_group_level`).

## 2. Brand vs. generic classification

CMS publishes a brand name and a generic name on every Part D drug row. After
normalization (`normalize_drug_name`: upper-case, punctuation collapsed), a row
is a **generic** product when the brand name equals the generic name, or is the
generic name followed by a formulation suffix. For example,
`Metformin Hcl Er / Metformin Hcl` and `Albuterol Sulfate Hfa / Albuterol
Sulfate` are generic. Anything else is **brand-name**, so
`Lipitor / Atorvastatin Calcium` is brand, and so are branded generics.

The rule is validated against CMS's own brand/generic claim split in the
prescriber-level file (`analyses/brand_share_vs_cms_classification.sql`). On the
2021 cohort (472,308 prescribers with an unsuppressed CMS split), the mean
brand claim share is 18.2% under this rule vs 17.7% under CMS's split, with a
prescriber-level correlation of 0.74. The first version of the rule, which
counted suffixed generics as brand, gave 22.0% and 0.72. See
[ADR 0002](decisions/0002-brand-generic-classification.md).

A generic name is **multi-source** (`int_part_d__drug_reference.is_multisource`)
when both a brand product and a generic product were dispensed nationally in
the data year, with at least `min_generic_fills_for_equivalence` (default
1,000) generic 30-day fills. It is a **single-brand equivalent**
(`is_single_brand_equivalent`) when it is multi-source and has exactly one
brand product, so the brand and the generic are the same medicine.

## 3. Industry payments and brand-name prescribing

**Exposure.** `is_industry_paid` = the prescriber received at least one Open
Payments general payment in program year 2021 that was tied to a drug or
biological. `industry_paid_definition: any` counts all general payments
instead. Research payments and ownership interests are not included.

### 3.1 Peer-adjusted comparison (headline)

Model: `mart_brand_peer_comparison`, `rpt_brand_comparison`.

This uses indirect standardization. For prescriber *i* with *F_i* 30-day fills:

```
expected_brand_fills_i = F_i x r(peer)
r(peer)                = brand fills / all fills among NOT-paid prescribers
                         in i's specialty x state
```

The reference falls back to specialty nationally, then all prescribers, when a
cell has fewer than `min_reference_peers` (default 10) unpaid prescribers.

```
O/E(group)             = sum(observed brand fills) / sum(expected brand fills)
pct_more_brand_fills   = (O/E(paid) / O/E(unpaid) - 1) x 100
```

`O/E(unpaid)` is 1 by construction within a cell. Dividing by it keeps the
metric exact when fallback levels are mixed; a dbt test warns if it drifts
outside 0.95-1.05.

**Resume/README headline:** `pct_more_brand_fills_peer_adjusted` on the
`industry_paid` row of `rpt_brand_comparison`.

### 3.2 Regression check

Module: `partd_risk.modeling.brand_effect`.

```
log E[brand_fills_i] = log(expected_brand_fills_i) + b * paid_i + g' * X_i
```

This is a Poisson GLM (quasi-likelihood, so non-integer fills are fine) with the
peer-expected brand fills as an offset. *X* holds beneficiary risk score, age,
dual-eligible share, low-income-subsidy share, female share, rurality and
centred log volume. Standard errors are clustered by peer group.
`exp(b) - 1` is reported with its 95% CI (`model_summary.json -> brand_effect`).

### 3.3 Dose-response

`rpt_brand_by_payment_tier` repeats the O/E comparison by payment tier
(`$0`, `$1-99`, `$100-999`, `$1,000-9,999`, `$10,000+`) and by payment profile
(meals only / other / speaker or consulting fees). `brand_tier_effects.csv`
gives the regression version.

### 3.4 Drug-matched analysis

`mart_drug_matched_prescribing` asks a sharper question: do prescribers paid in
connection with brand *B* write more of brand *B* than same-specialty
prescribers who were not? Brands named in payments to fewer than 25 cohort
prescribers are dropped.

### Interpretation

All of these are associations. Manufacturers choose whom to pay, and they can
target prescribers who already favour their products. The peer adjustment
removes differences explained by specialty, geography and patient mix. It does
not remove selection.

## 4. Generic-substitution savings

Model: `mart_generic_substitution_savings`, `rpt_savings_summary`.

For every multi-source drug *d* and specialty *s*:

```
expected brand fills (paid, s, d) = sum over paid prescribers of fills of d
                                    x brand share of d among UNPAID prescribers in s
net excess(s, d)                  = observed - expected           (signed, never floored)
savings(s, d)                     = net excess(s, d) x brand premium per fill(d)
brand premium per fill(d)         = max(national brand cost per fill - generic cost per fill, 0)
headline                          = sum of savings(s, d) over single-brand-equivalent drugs
```

Key choices:

- **Only multi-source drugs.** A single-source brand has no generic to switch to.
- **Signed net excess, no flooring.** Flooring each prescriber's excess, or
  each specialty x drug cell's, turns noise into savings. On the 2021 data,
  flooring cells produced about $661M even though paid prescribers' brand fills
  matched expected almost exactly in aggregate. Cells where paid prescribers
  wrote fewer brand fills than peers now offset cells where they wrote more.
- **Single-brand equivalents for the headline.** CMS pools every dosage form
  under one generic name, so when several brand products share it (Pennsaid
  topical solution vs generic diclofenac tablets, Duopa enteral suspension vs
  levodopa tablets) the "premium" compares different products. The headline
  keeps generic names with exactly one brand product. The all-multi-source
  total is reported as an upper bound.
- **Gross cost.** CMS `Tot_Drug_Cst` is before manufacturer rebates, which are
  confidential. `savings_sensitivity.csv` re-prices the premium with 15% and
  30% brand rebates and with only half of the excess fills switched.

**Resume/README headline:** `estimated_savings_usd` in `rpt_savings_summary`
(single-brand-equivalent drugs), reported in millions. It is an annual figure
because the data covers one year.

## 5. Peer-adjusted outlier score

Module: `partd_risk.modeling.peer_adjust`, `partd_risk.modeling.outlier_score`.
Feature spec: `config/outlier_score.yml`.

**Features.** All are oriented so that higher = more unusual in the risk
direction: brand fill share, multi-source brand share, cost per fill, cost per
beneficiary, fills per beneficiary, total volume, opioid claim share,
long-acting opioid share, and industry payments.

**Step 1: transform.** Logit for shares, log for costs and volumes, log1p for
payments.

**Step 2: regression-based peer adjustment.** For each feature:

```
f(metric_i) = alpha_peer(i) + beta' * casemix_i + e_i
```

This is estimated with the within transformation (peer-group fixed effects
without dummy variables), so it scales to about 1M prescribers. The case-mix
controls are the beneficiary variables from section 3.2. A missing control is
median-imputed and gets a missingness indicator.

**Step 3: robust z.** `z = (e - median(e)) / (1.4826 x MAD(e))`. A median/MAD
scale stops a handful of extreme prescribers from inflating the spread and
hiding one another.

**Step 4: combine with weights learned on earlier exclusions.** Two candidate
scores are built from the clipped z-scores `c_if = min(max(z_if, 0), 8)`:

```
equal weights:    score_i = mean_f c_if
learned weights:  score_i = sum_f w_f x c_if,  w_f >= 0
```

The learned weights come from an L2-penalised logistic regression of the
development outcome (below) on `c_if`, with every slope constrained to be
non-negative (`partd_risk.modeling.weights`). The constraint keeps the score
readable: every metric can only add risk. Only the risk direction counts
(negative z is clipped to 0), each feature is capped at 8 so one metric cannot
dominate, and a missing metric scores 0, so missing data can never raise a
score.

The peer adjustment itself never sees an outcome. The exclusion columns are
dropped from the feature table before steps 1-3 (`pipeline.run_model`).

## 6. Validation against later OIG exclusions

Module: `partd_risk.evaluation.lift`, `partd_risk.pipeline`.
Design record: [ADR 0007](decisions/0007-temporal-holdout-for-the-score.md).

**Outcome.** A prescriber's first LEIE exclusion after the data year.
Prescribers excluded on or before 31 Dec 2021 are not in the cohort (rule 4).

**Temporal split** (`weighting.split_date` in `config/outlier_score.yml`):

| Window | Exclusions | Used for |
|---|---|---|
| Development | 1 Jan 2022 - 31 Dec 2023 | learning the weights; choosing equal vs learned weights (by average precision) |
| Test | 1 Jan 2024 - 31 Jul 2026 (pinned, dbt var `outcome_window_end`) | the headline, measured once; never used for fitting or choosing |

Prescribers excluded in the development window are removed from the test
population, since they were already excluded. In the development fit, test-window
prescribers count as not excluded, which is what was known at the time.

**Metrics.** For the top *k* share of scores in the test population:

```
capture_share(k) = test-window exclusions in top k / all test-window exclusions
lift(k)          = capture_share(k) / k
```

**Resume/README headline:** test-window `lift(1%)` of the selected score: "the
top 1% captured *X*x the expected share of later Medicare exclusions". A 95%
percentile-bootstrap CI (1,000 resamples of prescribers) is reported with it,
along with AUROC, average precision, and lift at 0.1%-20%.

**Baselines reported next to it, on the same test population:**

- peer-adjusted, equal weights (`equal_weights`);
- equal weights without peer adjustment (`unadjusted`);
- each feature on its own, in both windows (`single_feature_lift.csv`).

## 7. Robustness checks

| Check | Where |
|---|---|
| Peer-adjusted vs. crude brand gap | `rpt_brand_comparison.pct_more_brand_fills_crude` |
| Multi-source-only brand gap | `rpt_brand_comparison.pct_more_multisource_brand_fills_peer_adjusted` |
| Regression with case-mix controls | `model_summary.json -> brand_effect` |
| Drug-matched payments | `mart_drug_matched_prescribing` |
| Payment definition (drug-related vs. any) | `dbt build --vars '{industry_paid_definition: any}'` |
| Minimum volume / peer size | `--vars '{min_total_fills: 250, min_peer_group_size: 50}'` |
| Savings under rebates / partial switching | `savings_sensitivity.csv` |
| Score without peer adjustment / equal weights | `model_summary.json -> test_by_score` |
| Name-based vs. CMS brand classification | `analyses/brand_share_vs_cms_classification.sql` |
