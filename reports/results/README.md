# reports/results

Written by `partd-risk model` and `partd-risk results` from a **real**
BigQuery run. The results step refuses to write here from synthetic data.

| File | Contents |
|---|---|
| `headline_metrics.json` | Every headline number with CIs and sensitivity analyses |
| `resume_bullets.md` | The project bullets with placeholders filled |
| `model_summary.json` | Outlier-score evaluation and brand regression summary |
| `lift_curve.csv` | Lift / capture share at 0.1%-20%, peer-adjusted vs. unadjusted |
| `single_feature_lift.csv` | Lift at 1% for each feature alone |
| `feature_ablation.csv` | Lift at 1% when each feature is dropped |
| `captured_exclusion_themes.csv` | Kinds of exclusions the top 1% captured |
| `brand_tier_effects.csv` | Regression rate ratios by payment tier |
| `brand_effect_glm_summary.txt` | Full GLM output |
| `peer_adjustment_diagnostics.csv` | Per-feature coverage, within-R2, case-mix coefficients |
| `savings_sensitivity.csv` | Savings under rebate / switching scenarios |

Definitions: `docs/methodology.md`. Placeholder mapping: `docs/results_placeholders.md`.
