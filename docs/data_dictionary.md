# Data dictionary

Generated from the dbt model YAML by `partd-risk data-dictionary`; do not edit by hand.
Run `dbt docs generate && dbt docs serve` for the full lineage graph.

## Staging

### `stg_leie__exclusions`

Typed OIG exclusions. Individuals and entities are both kept.

### `stg_nppes__providers`

Typed NPPES registry snapshot, one row per NPI.

| Column | Description |
|---|---|
| `entity_type_code` | 1 = individual, 2 = organization. NULL for deactivated NPIs. |
| `primary_taxonomy_code` | NUCC taxonomy code flagged as primary (else slot 1). |

### `stg_open_payments__general_payments`

Typed Open Payments general payments with a drug-related flag.

| Column | Description |
|---|---|
| `npi` | Covered recipient NPI (populated from program year 2021). NULL for teaching hospitals and for records CMS could not match to an NPI. |
| `is_drug_related` | Any attached product is a drug or biological. |

### `stg_part_d__prescriber`

Typed Part D prescriber-level summary with beneficiary case-mix.

| Column | Description |
|---|---|
| `entity_code` | `I` = individual, `O` = organization. |
| `ruca_code` | Rural-Urban Commuting Area code of the prescriber ZIP. |
| `is_rural` | RUCA code 4 or above (micropolitan, small town or rural). |
| `bene_avg_risk_score` | Average CMS-HCC risk score of the prescriber's beneficiaries. |

### `stg_part_d__prescriber_drug`

Typed Part D prescriber x drug rows with a normalized brand/generic key and an `is_brand` flag. Rows without a valid 10-digit NPI are dropped.

| Column | Description |
|---|---|
| `prescriber_drug_id` | Surrogate key over NPI, brand key and generic key. |
| `npi` | Prescriber National Provider Identifier (10 digits). |
| `brand_name_key` | Upper-cased brand name with punctuation collapsed. |
| `generic_name_key` | Upper-cased generic name with punctuation collapsed. |
| `is_brand` | True when the normalized brand name is neither the generic name nor the generic name followed by a formulation suffix (ER, HFA, ODT, ...). |
| `total_30day_fills` | Claims standardized to 30-day supplies (CMS `Tot_30day_Fills`). |
| `total_drug_cost` | Gross drug cost (ingredient cost, dispensing fee, sales tax, vaccine administration fee) paid by the Part D plan, beneficiary and other payers. Not net of manufacturer rebates. |

## Intermediate

### `int_exclusions__by_npi`

OIG exclusion history per NPI relative to the data year and outcome window.

| Column | Description |
|---|---|
| `days_to_window_exclusion` | Days from the end of the data year to the first in-window exclusion. |

### `int_part_d__drug_reference`

National brand vs generic volume and price per 30-day fill for every generic name. `is_multisource` marks drugs where both a brand and a generic version were dispensed; `brand_premium_per_fill` is the gap in average gross cost per fill between the two.

| Column | Description |
|---|---|
| `brand_premium_per_fill` | max(brand cost per fill - generic cost per fill, 0); NULL unless multi-source. |
| `is_single_brand_equivalent` | Multi-source and exactly one brand product for the generic name, so the brand-vs-generic price gap compares the same product. Headline savings set. |

### `int_payments__drug_matched`

NPI x product pairs where a payment named a specific drug or biological.

### `int_payments__prescriber_summary`

Industry general payments per NPI for the matching program year.

### `int_prescribers__cohort`

Every Part D prescriber with utilization, payments, exclusions, NPPES profile, the cohort decision and the assigned peer group.

| Column | Description |
|---|---|
| `cohort_exclusion_reason` | First cohort rule the prescriber fails; NULL when in the cohort. |
| `is_industry_paid` | Received at least one general payment in the program year. By default only drug/biological-related payments count (var `industry_paid_definition`). |

### `int_prescribers__fill_summary`

Per-prescriber brand, generic and multi-source fill totals.

## Marts

### `dim_drugs`

Drug dimension at generic-name grain with national pricing.

### `fct_prescribers`

One row per Part D prescriber NPI for the data year. Combines Part D utilization, brand/generic fills, Open Payments, OIG exclusions and the NPPES profile, with cohort flags and peer groups. All analysis marts filter to `in_cohort`.

| Column | Description |
|---|---|
| `in_cohort` | Passes every cohort rule (see int_prescribers__cohort). |
| `brand_fill_share` | Brand-name 30-day fills / all 30-day fills (drug-level file). |
| `multisource_brand_share` | Brand share among drugs with a nationally dispensed generic equivalent. |
| `cms_brand_claim_share` | Brand share using CMS's own brand/generic classification from the prescriber-level file. Used to validate the name-based classification (analyses/brand_share_vs_cms_classification.sql). |
| `cost_per_fill` | Gross drug cost per 30-day fill. |
| `opioid_claim_share` | Opioid claims / all claims. |
| `payment_tier` | Total general payments bucketed by var `payment_tier_breaks`. |
| `excluded_in_window` | First OIG exclusion falls after the data year (validation outcome). Never used as a model input. |

### `mart_brand_peer_comparison`

Observed vs expected brand-name fills per cohort prescriber, where expected comes from unpaid peers in the same specialty and state (indirect standardization). Source for the "X% more brand-name fills" headline.

| Column | Description |
|---|---|
| `reference_brand_share` | Brand fill share of unpaid peers used as the reference rate. |
| `expected_brand_fills` | drug_detail_fills x reference_brand_share. |
| `brand_oe_ratio` | brand_fills / expected_brand_fills. |
| `payment_profile` | Type of industry relationship (none, meals only, other, speaker/consulting). |

### `mart_drug_matched_prescribing`

For brands named in industry payments to at least 25 cohort prescribers: observed vs expected fills of that brand among the prescribers paid in connection with it, relative to same-specialty prescribers who were not.

| Column | Description |
|---|---|
| `oe_ratio` | Observed / expected fills of the paid-for brand. |

### `mart_generic_substitution_savings`

Change in gross Part D drug cost if industry-paid prescribers used brand vs generic versions of each multi-source drug at the rate of unpaid same-specialty peers, at specialty x drug grain. Signed: negative cells (paid prescribers below their peers) offset positive ones.

| Column | Description |
|---|---|
| `net_excess_brand_fills` | Observed - expected brand fills in the cell (signed, not floored). |
| `estimated_savings_usd` | net_excess_brand_fills x national brand premium per 30-day fill (signed). |

### `mart_outlier_features`

Feature table for the peer-adjusted outlier score (Python). One row per cohort prescriber. Exclusion columns are for evaluation only.

## Reporting

### `rpt_brand_by_payment_tier`

Peer-adjusted brand O/E by payment tier and payment profile (dose-response).

### `rpt_brand_comparison`

Headline table: industry-paid vs not-paid prescribers, crude and peer-adjusted brand-name fill rates. `pct_more_brand_fills_peer_adjusted` on the `industry_paid` row is the resume/README headline.

| Column | Description |
|---|---|
| `brand_oe_ratio` | Sum of observed / sum of expected brand fills. |
| `pct_more_brand_fills_peer_adjusted` | (O/E paid / O/E unpaid - 1) x 100. |

### `rpt_cohort_flow`

CONSORT-style cohort flow.

### `rpt_data_provenance`

Load provenance for every raw table, including the synthetic flag.

### `rpt_exclusion_outcomes`

Later OIG exclusions among cohort prescribers by year and theme.

### `rpt_savings_by_drug`

Savings by multi-source drug; rank and share within the headline set.

### `rpt_savings_summary`

One-row summary of the generic-substitution savings estimate. Headline columns cover single-brand-product drugs; *_all_multisource columns include every multi-source drug (upper bound).

| Column | Description |
|---|---|
| `estimated_savings_usd` | Net (signed) savings summed over every specialty x drug cell. |

### `rpt_source_row_counts`

Row counts of every raw source table.

### `rpt_specialty_summary`

Specialty-level payments, brand prescribing, savings and later exclusions.

### `rpt_state_summary`

State-level view for the Tableau map.

## Post Ml

### `fct_prescriber_risk`

Cohort prescribers joined to their outlier score. Contains identifiers; do not export. Built after `partd-risk model`.

### `rpt_outlier_by_segment`

Top-1% share and captured later exclusions by specialty and by state.

### `rpt_top_feature_mix`

Most influential feature among top-1% prescribers.
