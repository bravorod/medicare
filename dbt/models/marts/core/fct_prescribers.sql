{{
    config(
        cluster_by=['prescriber_specialty', 'prescriber_state'] if target.type == 'bigquery' else none
    )
}}

{#
    Prescriber fact table: one row per Part D prescriber NPI for the data year,
    with rates used across the analysis. Filter on `in_cohort` for analysis.
#}

with cohort as (

    select * from {{ ref('int_prescribers__cohort') }}

),

regions as (

    select state_code, census_region, census_division
    from {{ ref('state_regions') }}

)

select
    cohort.*,
    regions.census_region,
    regions.census_division,

    {{ safe_divide('cohort.brand_fills', 'cohort.drug_detail_fills') }}             as brand_fill_share,
    {{ safe_divide('cohort.multisource_brand_fills', 'cohort.multisource_fills') }} as multisource_brand_share,
    {{ safe_divide('cohort.cms_brand_claims', 'cohort.total_claims') }}             as cms_brand_claim_share,
    {{ safe_divide('cohort.total_drug_cost', 'cohort.total_30day_fills') }}         as cost_per_fill,
    {{ safe_divide('cohort.total_drug_cost', 'cohort.total_beneficiaries') }}       as cost_per_beneficiary,
    {{ safe_divide('cohort.total_30day_fills', 'cohort.total_beneficiaries') }}     as fills_per_beneficiary,
    {{ safe_divide('cohort.opioid_claims', 'cohort.total_claims') }}                as opioid_claim_share,
    {{ safe_divide('cohort.opioid_long_acting_claims', 'cohort.opioid_claims') }}   as opioid_long_acting_share,
    {{ safe_divide('cohort.lis_claims', 'cohort.total_claims') }}                   as lis_claim_share,
    {{ safe_divide('cohort.bene_dual_count', 'cohort.bene_dual_count + cohort.bene_nondual_count') }}
                                                                                    as dual_eligible_share,
    {{ safe_divide('cohort.bene_female_count', 'cohort.bene_female_count + cohort.bene_male_count') }}
                                                                                    as female_share

from cohort
left join regions
    on cohort.prescriber_state = regions.state_code
