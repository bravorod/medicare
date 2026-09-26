{#
    Dose-response: peer-adjusted brand O/E by payment tier and by payment
    profile (meals only vs speaker/consulting). Both are stacked into one table
    with a `dimension` column for Tableau.
#}

with prescribers as (

    select * from {{ ref('mart_brand_peer_comparison') }}

),

by_tier as (

    select
        'payment_tier'                                                  as dimension,
        payment_tier                                                    as dimension_value,
        count(*)                                                        as n_prescribers,
        sum(drug_detail_fills)                                          as total_fills,
        sum(brand_fills)                                                as observed_brand_fills,
        sum(expected_brand_fills)                                       as expected_brand_fills,
        avg(total_payment_usd)                                          as avg_payment_usd
    from prescribers
    group by payment_tier

),

by_profile as (

    select
        'payment_profile'                                               as dimension,
        payment_profile                                                 as dimension_value,
        count(*)                                                        as n_prescribers,
        sum(drug_detail_fills)                                          as total_fills,
        sum(brand_fills)                                                as observed_brand_fills,
        sum(expected_brand_fills)                                       as expected_brand_fills,
        avg(total_payment_usd)                                          as avg_payment_usd
    from prescribers
    group by payment_profile

),

stacked as (

    select * from by_tier
    union all
    select * from by_profile

)

select
    *,
    {{ safe_divide('observed_brand_fills', 'total_fills') }}            as crude_brand_share,
    {{ safe_divide('observed_brand_fills', 'expected_brand_fills') }}   as brand_oe_ratio,
    100 * ({{ safe_divide('observed_brand_fills', 'expected_brand_fills') }} - 1)
                                                                        as pct_vs_expected
from stacked
