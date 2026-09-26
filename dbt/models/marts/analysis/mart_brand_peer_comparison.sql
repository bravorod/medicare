{#
    Peer-adjusted brand prescribing, one row per cohort prescriber.

    Indirect standardization: each prescriber's expected brand fills are their
    own total fills x the brand share of NOT-industry-paid prescribers in the
    same specialty and state (falling back to specialty nationally, then all
    prescribers, when there are fewer than var('min_reference_peers')
    unpaid peers). Observed / expected > 1 means more brand-name fills than
    comparable unpaid peers writing the same volume.
#}

{%- set min_ref = var('min_reference_peers') %}

with cohort as (

    select * from {{ ref('fct_prescribers') }}
    where in_cohort

),

unpaid as (

    select * from cohort
    where not is_industry_paid

),

ref_specialty_state as (

    select
        prescriber_specialty,
        prescriber_state,
        count(*)                                                                as n_ref,
        {{ safe_divide('sum(brand_fills)', 'sum(drug_detail_fills)') }}         as brand_share,
        {{ safe_divide('sum(multisource_brand_fills)', 'sum(multisource_fills)') }}
                                                                                as multisource_brand_share
    from unpaid
    group by prescriber_specialty, prescriber_state

),

ref_specialty as (

    select
        prescriber_specialty,
        count(*)                                                                as n_ref,
        {{ safe_divide('sum(brand_fills)', 'sum(drug_detail_fills)') }}         as brand_share,
        {{ safe_divide('sum(multisource_brand_fills)', 'sum(multisource_fills)') }}
                                                                                as multisource_brand_share
    from unpaid
    group by prescriber_specialty

),

ref_all as (

    select
        {{ safe_divide('sum(brand_fills)', 'sum(drug_detail_fills)') }}         as brand_share,
        {{ safe_divide('sum(multisource_brand_fills)', 'sum(multisource_fills)') }}
                                                                                as multisource_brand_share
    from unpaid

),

referenced as (

    select
        cohort.npi,
        cohort.prescriber_specialty,
        cohort.prescriber_state,
        cohort.census_region,
        cohort.peer_group_id,
        cohort.is_industry_paid,
        cohort.payment_tier,
        cohort.total_payment_usd,
        cohort.drug_related_payment_usd,
        cohort.n_manufacturers,
        cohort.food_beverage_usd,
        cohort.speaker_faculty_usd,
        cohort.consulting_usd,
        cohort.drug_detail_fills,
        cohort.brand_fills,
        cohort.multisource_fills,
        cohort.multisource_brand_fills,
        case
            when coalesce(ss.n_ref, 0) >= {{ min_ref }} then 'specialty_state'
            when coalesce(s.n_ref, 0) >= {{ min_ref }} then 'specialty_national'
            else 'all_prescribers'
        end                                                                     as reference_level,
        case
            when coalesce(ss.n_ref, 0) >= {{ min_ref }} then ss.brand_share
            when coalesce(s.n_ref, 0) >= {{ min_ref }} then s.brand_share
            else ref_all.brand_share
        end                                                                     as reference_brand_share,
        coalesce(
            case
                when coalesce(ss.n_ref, 0) >= {{ min_ref }} then ss.multisource_brand_share
                when coalesce(s.n_ref, 0) >= {{ min_ref }} then s.multisource_brand_share
            end,
            ref_all.multisource_brand_share
        )                                                                       as reference_multisource_brand_share

    from cohort
    left join ref_specialty_state as ss
        on cohort.prescriber_specialty = ss.prescriber_specialty
       and cohort.prescriber_state = ss.prescriber_state
    left join ref_specialty as s
        on cohort.prescriber_specialty = s.prescriber_specialty
    cross join ref_all

)

select
    *,
    case
        when speaker_faculty_usd + consulting_usd > 0 then '3: speaker / consulting fees'
        when food_beverage_usd > 0 and food_beverage_usd >= total_payment_usd - 0.005 then '1: meals only'
        when total_payment_usd > 0 then '2: other payments'
        else '0: none'
    end                                                                         as payment_profile,
    drug_detail_fills * reference_brand_share                                   as expected_brand_fills,
    multisource_fills * reference_multisource_brand_share                       as expected_multisource_brand_fills,
    {{ safe_divide('brand_fills', 'drug_detail_fills * reference_brand_share') }}
                                                                                as brand_oe_ratio
from referenced
