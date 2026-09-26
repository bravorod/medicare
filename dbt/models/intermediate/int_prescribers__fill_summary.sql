{#
    Per-prescriber brand / generic fill totals built up from drug-level rows,
    including the multi-source subset (brand drugs with a dispensed generic
    equivalent) that drives the savings estimate.
#}

with fills as (

    select * from {{ ref('stg_part_d__prescriber_drug') }}

),

drugs as (

    select generic_name_key, is_multisource, brand_premium_per_fill
    from {{ ref('int_part_d__drug_reference') }}

),

joined as (

    select
        fills.npi,
        fills.generic_name_key,
        fills.is_brand,
        fills.total_30day_fills,
        fills.total_drug_cost,
        coalesce(drugs.is_multisource, false)       as is_multisource,
        coalesce(drugs.brand_premium_per_fill, 0)   as brand_premium_per_fill

    from fills
    left join drugs
        on fills.generic_name_key = drugs.generic_name_key

)

select
    npi,
    count(*)                                                                        as n_drug_rows,
    count(distinct generic_name_key)                                                as n_distinct_generics,
    sum(total_30day_fills)                                                          as drug_detail_fills,
    sum(total_drug_cost)                                                            as drug_detail_cost,
    sum(case when is_brand then total_30day_fills else 0 end)                       as brand_fills,
    sum(case when is_brand then total_drug_cost else 0 end)                         as brand_cost,
    sum(case when not is_brand then total_30day_fills else 0 end)                   as generic_fills,
    sum(case when is_multisource then total_30day_fills else 0 end)                 as multisource_fills,
    sum(case when is_multisource and is_brand then total_30day_fills else 0 end)    as multisource_brand_fills,
    sum(
        case when is_multisource and is_brand
            then total_30day_fills * brand_premium_per_fill else 0 end
    )                                                                               as multisource_brand_premium_usd

from joined
group by npi
