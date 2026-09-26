# Tableau dashboard: Part D Prescribing Risk

The dashboard is built in Tableau Desktop / Tableau Public from the
de-identified CSV extracts that `partd-risk export-tableau` writes to
`tableau/extracts/`. This file is the build spec: data sources, calculated
fields and the layout of each sheet, so the workbook can be rebuilt or
reviewed without opening Tableau.

**Published workbook:** _add the Tableau Public URL here after publishing_
(also update `url` in `dbt/models/exposures.yml`).

## Audience and questions

Non-technical stakeholders (policy, program integrity, leadership). The
dashboard answers three questions, one tab each:

1. Do prescribers who receive industry payments write more brand-name drugs
   than comparable peers?
2. What would it be worth if they matched their peers?
3. Does a simple outlier score point to prescribers who were later excluded
   from Medicare?

## Data sources (extracts)

| Extract | Grain | Feeds |
|---|---|---|
| `brand_comparison.csv` | payment group (2 rows) | KPI tiles |
| `brand_by_payment_tier.csv` | dimension x value | Dose-response bars |
| `drug_matched_prescribing.csv` | brand | Paid-for brand O/E |
| `savings_summary.csv` | 1 row | Savings KPI |
| `savings_by_drug.csv` | generic drug | Top drugs bar |
| `specialty_summary.csv` | specialty | Specialty table / bars |
| `state_summary.csv` | state | Filled map |
| `cohort_flow.csv` | step | Methods panel |
| `model_lift_curve.csv` | score x k | Gains chart |
| `model_single_feature_lift.csv` | feature | Feature comparison |
| `model_learned_weights.csv` | feature | Learned weight per feature |
| `model_score_selection.csv` | score | Development-window comparison of candidate scores |
| `outlier_by_segment.csv` | dimension x value | Where top-1% sits |
| `top_feature_mix.csv` | feature | What drives the flags |
| `exclusion_outcomes.csv` | year x theme | Outcome context |
| `prescribers_deidentified.csv` (optional) | pseudonymous prescriber | Scatter / distributions |

## Calculated fields

```text
// Brand gap vs. peers (%)                       [brand_by_payment_tier]
([Brand Oe Ratio] - 1)

// Paid brand O/E, formatted                     [state_summary, specialty_summary]
[Paid Brand Oe Ratio] - 1

// Savings ($M)                                  [savings_by_drug]
[Estimated Savings Usd] / 1000000

// Drug label                                    [savings_by_drug]
PROPER([Generic Name]) + " (" + [Example Brand Name] + ")"

// Lift label                                    [model_lift_curve]
STR(ROUND([Lift], 1)) + "x"

// Is headline k                                 [model_lift_curve]
ABS([K] - 0.01) < 0.00001

// Tier label (strip sort prefix)                [brand_by_payment_tier]
MID([Dimension Value], FIND([Dimension Value], ": ") + 2)
```

Sort tiers by `Dimension Value` (the `0:`-`4:` prefixes keep payment tiers in
order), and display `Tier label`.

## Layout

### Tab 1: Payments & prescribing

- **KPI row** (text tiles): % of prescribers industry-paid; brand-name fills
  vs. peers (`pct_more_brand_fills_peer_adjusted`, industry_paid row);
  prescribers analysed.
- **Dose-response bar** (`brand_by_payment_tier`, dimension = payment_tier):
  x = tier label, y = brand gap %, one color, value labels on the bars,
  reference line at 0.
- **Relationship type bar** (dimension = payment_profile): same encoding.
- **Map** (`state_summary`): filled map of `Paid Brand O/E - 1`, diverging
  palette centred on 0 (blue = below peers, red = above), tooltip with n and %
  paid.

### Tab 2: Savings

- **KPI tile:** estimated savings ($M) with the rebate-adjusted range from
  `reports/results/savings_sensitivity.csv` in the subtitle.
- **Top 15 drugs** (`savings_by_drug`, `savings_rank <= 15`): horizontal bars,
  one color, $M labels.
- **By specialty** (`specialty_summary`): bar of `estimated_savings_usd`.

### Tab 3: Early-warning score

- **Gains chart** (`model_lift_curve`): x = k (log scale), y = capture share on the
  held-out 2024+ exclusions, one line each for the selected score and `unadjusted`, thin gray diagonal
  for random. Annotate the `Is headline k` point with its lift label.
- **Feature panel** (`model_single_feature_lift`): lift at 1% per feature,
  sorted.
- **What drives flags** (`top_feature_mix`): bars of top-1% prescribers by
  top feature.
- **Caveat text box:** "A high score means worth a closer look, not
  wrongdoing." Copy the wording from `docs/limitations_and_ethics.md`.

### Methods panel (all tabs, collapsible)

Cohort flow (`cohort_flow`), data year, sources, link to the GitHub repo.

## Style

- Categorical: blue `#2a78d6` for the primary series, orange `#eb6834` for the
  comparison series. Nothing else.
- Diverging (map): blue `#2a78d6` <-> gray `#f0efec` <-> red `#e34948`.
- Text in dark gray, never in the series color. Light gridlines, no borders.
- Every chart has a one-line subtitle saying what "expected" means.

## Refreshing

```bash
partd-risk export-tableau --target bigquery
```

then in Tableau: *Data > Refresh All Extracts* and republish.
