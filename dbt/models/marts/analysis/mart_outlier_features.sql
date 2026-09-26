{#
    Model-ready feature table for the peer-adjusted outlier score, one row per
    cohort prescriber. Outcome columns (excluded_in_window, ...) are carried
    for evaluation only; the Python scorer never uses them as inputs.
#}

select
    npi,
    peer_group_id,
    peer_group_level,
    prescriber_specialty,
    prescriber_state,
    census_region,

    -- scored metrics (higher = more unusual in the risk direction)
    brand_fill_share,
    multisource_brand_share,
    cost_per_fill,
    cost_per_beneficiary,
    fills_per_beneficiary,
    total_30day_fills,
    opioid_claim_share,
    opioid_long_acting_share,
    total_payment_usd,
    n_manufacturers,

    -- case-mix controls
    bene_avg_risk_score,
    bene_avg_age,
    dual_eligible_share,
    lis_claim_share,
    female_share,
    case when is_rural then 1 else 0 end                as is_rural,

    -- context
    is_industry_paid,
    payment_tier,
    total_drug_cost,
    total_beneficiaries,

    -- evaluation only
    excluded_in_window,
    window_exclusion_date,
    window_exclusion_type_code,
    window_exclusion_theme,
    days_to_window_exclusion,
    (select max(window_end) from {{ ref('int_exclusions__by_npi') }})    as outcome_window_end

from {{ ref('fct_prescribers') }}
where in_cohort
