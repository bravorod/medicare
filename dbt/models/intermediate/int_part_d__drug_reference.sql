{#
    National reference table at generic-name grain.

    For every generic name we measure brand and generic volume and cost per
    30-day fill. A generic name is "multi-source" when both a brand product and
    a generic product were dispensed nationally in the data year.

    CMS pools every dosage form under one generic name, so when several brand
    products share a generic name (e.g. Pennsaid topical solution vs generic
    diclofenac tablets) the brand-vs-generic price gap compares different
    products. `is_single_brand_equivalent` keeps the clean cases, with exactly
    one brand product; these drive the headline savings estimate (ADR 0005).
#}

with fills as (

    select * from {{ ref('stg_part_d__prescriber_drug') }}

),

by_generic as (

    select
        generic_name_key,
        min(generic_name)                                                           as generic_name,
        min(case when is_brand then brand_name end)                                 as example_brand_name,
        count(distinct case when is_brand then brand_name_key end)                  as n_brand_products,
        count(distinct npi)                                                         as n_prescribers,
        sum(case when is_brand then total_30day_fills else 0 end)                   as brand_fills,
        sum(case when is_brand then total_drug_cost else 0 end)                     as brand_cost,
        sum(case when not is_brand then total_30day_fills else 0 end)               as generic_fills,
        sum(case when not is_brand then total_drug_cost else 0 end)                 as generic_cost,
        sum(total_30day_fills)                                                      as total_fills,
        sum(total_drug_cost)                                                        as total_cost

    from fills
    group by generic_name_key

),

priced as (

    select
        *,
        {{ safe_divide('brand_cost', 'brand_fills') }}                              as brand_cost_per_fill,
        {{ safe_divide('generic_cost', 'generic_fills') }}                          as generic_cost_per_fill,
        brand_fills > 0                                                             as has_brand_version,
        generic_fills >= {{ var('min_generic_fills_for_equivalence') }}             as has_generic_version

    from by_generic

)

select
    generic_name_key,
    generic_name,
    example_brand_name,
    n_brand_products,
    n_prescribers,
    brand_fills,
    brand_cost,
    generic_fills,
    generic_cost,
    total_fills,
    total_cost,
    brand_cost_per_fill,
    generic_cost_per_fill,
    has_brand_version,
    has_generic_version,
    has_brand_version and has_generic_version                                       as is_multisource,
    has_brand_version and has_generic_version and n_brand_products = 1              as is_single_brand_equivalent,
    case
        when has_brand_version and has_generic_version
            then {{ greatest_not_null('brand_cost_per_fill - generic_cost_per_fill', '0') }}
    end                                                                             as brand_premium_per_fill,
    {{ safe_divide('brand_fills', 'total_fills') }}                                 as national_brand_share

from priced
