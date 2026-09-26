{#
    State-level view for the Tableau map.
#}

with prescribers as (

    select * from {{ ref('mart_brand_peer_comparison') }}

),

outcomes as (

    select npi, excluded_in_window, total_drug_cost
    from {{ ref('fct_prescribers') }}
    where in_cohort

),

regions as (

    select * from {{ ref('state_regions') }}

),

by_state as (

    select
        prescribers.prescriber_state,
        count(*)                                                                    as n_prescribers,
        sum(case when prescribers.is_industry_paid then 1 else 0 end)               as n_industry_paid,
        sum(prescribers.total_payment_usd)                                          as total_payment_usd,
        sum(outcomes.total_drug_cost)                                               as total_drug_cost,
        sum(prescribers.drug_detail_fills)                                          as total_fills,
        sum(prescribers.brand_fills)                                                as brand_fills,
        sum(case when prescribers.is_industry_paid then prescribers.brand_fills else 0 end)
                                                                                    as paid_brand_fills,
        sum(case when prescribers.is_industry_paid then prescribers.expected_brand_fills else 0 end)
                                                                                    as paid_expected_brand_fills,
        sum(case when outcomes.excluded_in_window then 1 else 0 end)                as n_later_exclusions

    from prescribers
    inner join outcomes on prescribers.npi = outcomes.npi
    group by prescribers.prescriber_state

)

select
    by_state.*,
    regions.state_name,
    regions.census_region,
    {{ safe_divide('n_industry_paid', 'n_prescribers') }}                           as share_industry_paid,
    {{ safe_divide('brand_fills', 'total_fills') }}                                 as brand_fill_share,
    {{ safe_divide('paid_brand_fills', 'paid_expected_brand_fills') }}              as paid_brand_oe_ratio,
    1000 * {{ safe_divide('n_later_exclusions', 'n_prescribers') }}                 as later_exclusions_per_1000
from by_state
left join regions
    on by_state.prescriber_state = regions.state_code
