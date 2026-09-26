{#
    Savings estimate by drug. savings_rank and share_of_headline_savings are
    computed within the headline set (single brand product per generic name);
    other multi-source drugs are kept with a NULL rank for transparency.
#}

with cells as (

    select * from {{ ref('mart_generic_substitution_savings') }}

),

by_drug as (

    select
        generic_name_key,
        min(generic_name)                                               as generic_name,
        min(example_brand_name)                                         as example_brand_name,
        min(n_brand_products)                                           as n_brand_products,
        min(n_brand_products) = 1                                       as is_single_brand_equivalent,
        min(brand_premium_per_fill)                                     as brand_premium_per_fill,
        sum(n_paid_prescribers)                                         as n_paid_prescriber_cells,
        sum(paid_total_fills)                                           as paid_total_fills,
        sum(observed_brand_fills)                                       as observed_brand_fills,
        sum(expected_brand_fills)                                       as expected_brand_fills,
        sum(net_excess_brand_fills)                                     as net_excess_brand_fills,
        sum(estimated_savings_usd)                                      as estimated_savings_usd
    from cells
    group by generic_name_key

)

select
    *,
    case when is_single_brand_equivalent then
        row_number() over (
            partition by is_single_brand_equivalent
            order by estimated_savings_usd desc, generic_name_key
        )
    end                                                                         as savings_rank,
    case when is_single_brand_equivalent then
        {{ safe_divide(
            'estimated_savings_usd',
            '(select sum(estimated_savings_usd) from by_drug where is_single_brand_equivalent)'
        ) }}
    end                                                                         as share_of_headline_savings
from by_drug
