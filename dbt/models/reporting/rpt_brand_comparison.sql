{#
    Headline comparison: industry-paid vs not-paid prescribers.

    pct_more_brand_fills_peer_adjusted
        = (O/E among paid) / (O/E among unpaid) - 1, in percent.
    Unpaid O/E is ~1 by construction; dividing by it anyway keeps the metric
    exact when fallback reference levels are mixed.
#}

with prescribers as (

    select * from {{ ref('mart_brand_peer_comparison') }}

),

grouped as (

    select
        case when is_industry_paid then 'industry_paid' else 'not_industry_paid' end    as payment_group,
        count(*)                                                                        as n_prescribers,
        sum(drug_detail_fills)                                                          as total_fills,
        sum(brand_fills)                                                                as observed_brand_fills,
        sum(expected_brand_fills)                                                       as expected_brand_fills,
        sum(multisource_brand_fills)                                                    as observed_multisource_brand_fills,
        sum(expected_multisource_brand_fills)                                           as expected_multisource_brand_fills,
        sum(multisource_fills)                                                          as multisource_fills,
        sum(total_payment_usd)                                                          as total_payment_usd

    from prescribers
    group by 1

),

rated as (

    select
        *,
        {{ safe_divide('observed_brand_fills', 'total_fills') }}                        as crude_brand_share,
        {{ safe_divide('observed_brand_fills', 'expected_brand_fills') }}               as brand_oe_ratio,
        {{ safe_divide('observed_multisource_brand_fills', 'multisource_fills') }}      as crude_multisource_brand_share,
        {{ safe_divide('observed_multisource_brand_fills', 'expected_multisource_brand_fills') }}
                                                                                        as multisource_brand_oe_ratio
    from grouped

),

unpaid as (

    select * from rated where payment_group = 'not_industry_paid'

)

select
    rated.*,
    100 * ({{ safe_divide('rated.brand_oe_ratio', 'unpaid.brand_oe_ratio') }} - 1)
                                                                        as pct_more_brand_fills_peer_adjusted,
    100 * ({{ safe_divide('rated.crude_brand_share', 'unpaid.crude_brand_share') }} - 1)
                                                                        as pct_more_brand_fills_crude,
    100 * ({{ safe_divide('rated.multisource_brand_oe_ratio', 'unpaid.multisource_brand_oe_ratio') }} - 1)
                                                                        as pct_more_multisource_brand_fills_peer_adjusted,
    100 * {{ safe_divide('rated.n_prescribers', '(select sum(n_prescribers) from rated)') }}
                                                                        as pct_of_cohort
from rated
cross join unpaid
