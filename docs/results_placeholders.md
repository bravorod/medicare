# Where each headline number comes from

The project summary has four placeholders. Each one is produced by
`partd-risk results` from a **real** BigQuery run. The command refuses to
produce them from synthetic data. It prints the filled bullets and writes them
to `reports/results/resume_bullets.md`, with full precision and confidence
intervals in `reports/results/headline_metrics.json`.

> Medicare Part D Prescribing Risk Analysis
> - Estimated **$[X]M** in Medicare savings by building a BigQuery and dbt pipeline over
>   **[X]M+** Part D, Open Payments, and provider records, finding industry-paid prescribers
>   wrote **[X]%** more brand-name fills than peers.
> - Built a peer-adjusted outlier score with regression in Python whose top 1% captured
>   **[X]x** the expected share of later Medicare exclusions, presenting findings in a
>   Tableau dashboard and memo for non-technical readers.

| Placeholder | JSON key (`headline_metrics.json`) | Source | Definition | Rounding |
|---|---|---|---|---|
| `$[X]M` savings | `savings.estimated_savings_usd_millions` | dbt `rpt_savings_summary` | Net (signed) excess brand fills written by industry-paid prescribers, relative to unpaid same-specialty peers, on drugs with a generic version and a single brand product, x national brand-minus-generic gross cost per fill ([methodology section 4](methodology.md#4-generic-substitution-savings)) | whole $M (1 decimal under $10M) |
| `[X]M+` records | `records.total_raw_records` | dbt `rpt_source_row_counts` | Rows loaded across the five raw tables (Part D by provider & drug, Part D by provider, Open Payments general, LEIE, NPPES) | floor to whole millions, then "+" |
| `[X]%` more brand-name fills | `brand_prescribing.pct_more_brand_fills_peer_adjusted` | dbt `rpt_brand_comparison` (row `industry_paid`) | (O/E brand fills of paid prescribers / O/E of unpaid) - 1, with expected fills taken from unpaid peers in the same specialty and state ([section 3.1](methodology.md#31-peer-adjusted-comparison-headline)) | whole % |
| `[X]x` exclusion capture | `outlier_score.lift` | Python `partd_risk.pipeline` / `evaluation.lift` (`model_summary.json`) | Share of held-out OIG exclusions (first exclusion from 2024 on) that fall in the top 1% of the peer-adjusted outlier score, divided by 1%. Score weights were learned on 2022-2023 exclusions only ([section 6](methodology.md#6-validation-against-later-oig-exclusions)) | 1 decimal |

Also fill in by hand:

| Placeholder | Value |
|---|---|
| `[Month Year]` | month you run and publish the analysis |
| `github.com/bravorod/[repo]` | `github.com/bravorod/medicare` |

## Numbers worth having ready in an interview

These are all in `headline_metrics.json`:

- `brand_prescribing.regression_pct_more` and its `regression_pct_ci95`: the
  same gap estimated by regression with case-mix controls.
- `brand_prescribing.pct_more_brand_fills_crude`: the gap before peer
  adjustment, to show what the adjustment does.
- `savings.sensitivity`: savings net of 15% / 30% brand rebates and with
  partial switching.
- `outlier_score.lift_ci95`, `events_captured` / `events_total`, `auroc`,
  `equal_weights_lift`, `unadjusted_lift`, `design`: how precise the lift is,
  what the out-of-time test looked like, and what learning the weights and the
  peer adjustment each added.
- `cohort.n_prescribers`, `cohort.share_industry_paid`.

## Wording

"Medicare savings" in the bullet is **potential** gross Part D drug-cost
savings, before manufacturer rebates. If an interviewer asks, the
rebate-adjusted range from `savings.sensitivity` is the honest answer.
