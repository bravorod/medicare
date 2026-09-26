{#
    One row per Part D prescriber NPI with everything needed downstream:
    utilization, brand/generic fills, payments, exclusion history, NPPES
    profile, the cohort decision (with the reason when excluded) and the peer
    group used for adjustment.

    Cohort rules (applied in order, first failing rule is recorded):
      1. individual prescriber (Part D entity code I / NPPES entity type 1)
      2. specialty and state present
      3. at least var('min_total_fills') 30-day fills in the drug-level file
      4. not already excluded by OIG on or before the end of the data year

    Peer group: specialty x state when that cell has at least
    var('min_peer_group_size') cohort members, else specialty nationally, else
    all prescribers.
#}

{%- set min_peers = var('min_peer_group_size') %}

with prescribers as (

    select * from {{ ref('stg_part_d__prescriber') }}

),

fills as (

    select * from {{ ref('int_prescribers__fill_summary') }}

),

payments as (

    select * from {{ ref('int_payments__prescriber_summary') }}

),

exclusions as (

    select * from {{ ref('int_exclusions__by_npi') }}

),

nppes as (

    select
        npi,
        entity_type_code,
        primary_taxonomy_code,
        practice_state,
        enumeration_date,
        deactivation_date
    from {{ ref('stg_nppes__providers') }}

),

joined as (

    select
        prescribers.npi,
        coalesce(
            prescribers.entity_code,
            case nppes.entity_type_code when 1 then 'I' when 2 then 'O' end
        )                                                                   as entity_code,
        prescribers.prescriber_last_or_org_name,
        prescribers.prescriber_first_name,
        prescribers.prescriber_credentials,
        prescribers.prescriber_specialty,
        prescribers.prescriber_state,
        prescribers.prescriber_zip5,
        prescribers.ruca_code,
        coalesce(prescribers.is_rural, false)                               as is_rural,

        -- utilization (prescriber-level file)
        prescribers.total_claims,
        prescribers.total_30day_fills,
        prescribers.total_drug_cost,
        prescribers.total_day_supply,
        prescribers.total_beneficiaries,
        prescribers.cms_brand_claims,
        prescribers.cms_generic_claims,
        prescribers.lis_claims,
        prescribers.opioid_claims,
        prescribers.opioid_long_acting_claims,
        prescribers.antibiotic_claims,
        prescribers.antipsychotic_ge65_claims,

        -- beneficiary case-mix
        prescribers.bene_avg_age,
        prescribers.bene_avg_risk_score,
        prescribers.bene_dual_count,
        prescribers.bene_nondual_count,
        prescribers.bene_female_count,
        prescribers.bene_male_count,

        -- brand / generic (drug-level file)
        coalesce(fills.n_distinct_generics, 0)                              as n_distinct_generics,
        coalesce(fills.drug_detail_fills, 0)                                as drug_detail_fills,
        coalesce(fills.drug_detail_cost, 0)                                 as drug_detail_cost,
        coalesce(fills.brand_fills, 0)                                      as brand_fills,
        coalesce(fills.brand_cost, 0)                                       as brand_cost,
        coalesce(fills.generic_fills, 0)                                    as generic_fills,
        coalesce(fills.multisource_fills, 0)                                as multisource_fills,
        coalesce(fills.multisource_brand_fills, 0)                          as multisource_brand_fills,
        coalesce(fills.multisource_brand_premium_usd, 0)                    as multisource_brand_premium_usd,

        -- industry payments
        coalesce(payments.n_payment_records, 0)                             as n_payment_records,
        coalesce(payments.n_manufacturers, 0)                               as n_manufacturers,
        coalesce(payments.total_payment_usd, 0)                             as total_payment_usd,
        coalesce(payments.drug_related_payment_usd, 0)                      as drug_related_payment_usd,
        coalesce(payments.n_drug_manufacturers, 0)                          as n_drug_manufacturers,
        coalesce(payments.food_beverage_usd, 0)                             as food_beverage_usd,
        coalesce(payments.speaker_faculty_usd, 0)                           as speaker_faculty_usd,
        coalesce(payments.consulting_usd, 0)                                as consulting_usd,
        coalesce(payments.travel_lodging_usd, 0)                            as travel_lodging_usd,
        {%- if var('industry_paid_definition') == 'any' %}
        coalesce(payments.total_payment_usd, 0) > 0                         as is_industry_paid,
        {%- else %}
        coalesce(payments.drug_related_payment_usd, 0) > 0                  as is_industry_paid,
        {%- endif %}
        {{ payment_tier('coalesce(payments.total_payment_usd, 0)') }}       as payment_tier,

        -- OIG exclusions
        coalesce(exclusions.excluded_before_window, false)                  as excluded_before_window,
        coalesce(exclusions.excluded_in_window, false)                      as excluded_in_window,
        exclusions.window_exclusion_date,
        exclusions.window_exclusion_type_code,
        exclusions.window_exclusion_theme,
        exclusions.days_to_window_exclusion,

        -- NPPES
        nppes.npi is not null                                               as is_in_nppes,
        nppes.primary_taxonomy_code,
        nppes.practice_state                                                as nppes_practice_state,
        nppes.enumeration_date                                              as nppes_enumeration_date,
        nppes.deactivation_date                                             as nppes_deactivation_date

    from prescribers
    left join fills on prescribers.npi = fills.npi
    left join payments on prescribers.npi = payments.npi
    left join exclusions on prescribers.npi = exclusions.npi
    left join nppes on prescribers.npi = nppes.npi

),

flagged as (

    select
        *,
        case
            when coalesce(entity_code, 'I') != 'I'                          then '1_not_individual'
            when prescriber_specialty is null or prescriber_state is null   then '2_missing_specialty_or_state'
            when drug_detail_fills < {{ var('min_total_fills') }}           then '3_below_min_fills'
            when excluded_before_window                                     then '4_excluded_before_window'
        end                                                                 as cohort_exclusion_reason

    from joined

),

specialty_state_sizes as (

    select prescriber_specialty, prescriber_state, count(*) as n_cohort
    from flagged
    where cohort_exclusion_reason is null
    group by prescriber_specialty, prescriber_state

),

specialty_sizes as (

    select prescriber_specialty, count(*) as n_cohort
    from flagged
    where cohort_exclusion_reason is null
    group by prescriber_specialty

),

grouped as (

    select
        flagged.*,
        flagged.cohort_exclusion_reason is null                             as in_cohort,
        case
            when flagged.cohort_exclusion_reason is not null then null
            when specialty_state_sizes.n_cohort >= {{ min_peers }} then 'specialty_state'
            when specialty_sizes.n_cohort >= {{ min_peers }} then 'specialty_national'
            else 'all_prescribers'
        end                                                                 as peer_group_level

    from flagged
    left join specialty_state_sizes
        on flagged.prescriber_specialty = specialty_state_sizes.prescriber_specialty
       and flagged.prescriber_state = specialty_state_sizes.prescriber_state
    left join specialty_sizes
        on flagged.prescriber_specialty = specialty_sizes.prescriber_specialty

)

select
    *,
    case peer_group_level
        when 'specialty_state' then prescriber_specialty || ' | ' || prescriber_state
        when 'specialty_national' then prescriber_specialty || ' | US'
        when 'all_prescribers' then 'All prescribers | US'
    end                                                                     as peer_group_id
from grouped
