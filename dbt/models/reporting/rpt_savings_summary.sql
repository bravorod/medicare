{#
    One-row summary of the generic-substitution savings estimate.

    Headline columns use drugs with a single brand product
    (is_single_brand_equivalent), where brand and generic are the same product.
    The *_all_multisource columns include every multi-source drug; they pool
    dosage forms under one generic name and are reported as an upper bound.
#}

with cells as (

    select * from {{ ref('mart_generic_substitution_savings') }}

),

headline as (

    select * from cells
    where is_single_brand_equivalent

)

select
    sum(estimated_savings_usd)                                          as estimated_savings_usd,
    sum(estimated_savings_usd) / 1e6                                    as estimated_savings_usd_millions,
    sum(net_excess_brand_fills)                                         as net_excess_brand_fills,
    sum(observed_brand_fills)                                           as observed_brand_fills,
    sum(expected_brand_fills)                                           as expected_brand_fills,
    sum(paid_total_fills)                                               as paid_equivalent_fills,
    count(distinct generic_name_key)                                    as n_drugs,
    count(distinct prescriber_specialty)                                as n_specialties,
    sum(case when estimated_savings_usd > 0 then 1 else 0 end)          as n_cells_positive,
    sum(case when estimated_savings_usd < 0 then 1 else 0 end)          as n_cells_negative,
    count(*)                                                            as n_cells,
    (select sum(estimated_savings_usd) from cells)                      as estimated_savings_usd_all_multisource,
    (select sum(estimated_savings_usd) from cells) / 1e6                as estimated_savings_usd_millions_all_multisource,
    (select count(distinct generic_name_key) from cells)                as n_drugs_all_multisource,
    {{ safe_divide('sum(paid_total_fills)', '(select sum(paid_total_fills) from cells)') }}
                                                                        as share_of_multisource_fills
from headline
