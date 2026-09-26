{#
    Specialty-level view for Tableau: payments, brand prescribing, savings and
    later exclusions.
#}

with prescribers as (

    select * from {{ ref('mart_brand_peer_comparison') }}

),

outcomes as (

    select npi, excluded_in_window
    from {{ ref('fct_prescribers') }}
    where in_cohort

),

savings as (

    select prescriber_specialty, sum(estimated_savings_usd) as estimated_savings_usd
    from {{ ref('mart_generic_substitution_savings') }}
    where is_single_brand_equivalent
    group by prescriber_specialty

),

by_specialty as (

    select
        prescribers.prescriber_specialty,
        count(*)                                                                    as n_prescribers,
        sum(case when prescribers.is_industry_paid then 1 else 0 end)               as n_industry_paid,
        sum(prescribers.total_payment_usd)                                          as total_payment_usd,
        sum(prescribers.drug_detail_fills)                                          as total_fills,
        sum(prescribers.brand_fills)                                                as brand_fills,
        sum(case when prescribers.is_industry_paid then prescribers.brand_fills else 0 end)
                                                                                    as paid_brand_fills,
        sum(case when prescribers.is_industry_paid then prescribers.expected_brand_fills else 0 end)
                                                                                    as paid_expected_brand_fills,
        sum(case when outcomes.excluded_in_window then 1 else 0 end)                as n_later_exclusions

    from prescribers
    inner join outcomes on prescribers.npi = outcomes.npi
    group by prescribers.prescriber_specialty

)

select
    by_specialty.*,
    {{ safe_divide('n_industry_paid', 'n_prescribers') }}                           as share_industry_paid,
    {{ safe_divide('brand_fills', 'total_fills') }}                                 as brand_fill_share,
    {{ safe_divide('paid_brand_fills', 'paid_expected_brand_fills') }}              as paid_brand_oe_ratio,
    coalesce(savings.estimated_savings_usd, 0)                                      as estimated_savings_usd
from by_specialty
left join savings
    on by_specialty.prescriber_specialty = savings.prescriber_specialty
