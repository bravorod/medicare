{#
    Drug dimension at generic-name grain with national brand/generic pricing.
#}

select
    generic_name_key,
    generic_name,
    example_brand_name,
    n_brand_products,
    n_prescribers,
    brand_fills,
    generic_fills,
    total_fills,
    total_cost,
    brand_cost_per_fill,
    generic_cost_per_fill,
    brand_premium_per_fill,
    national_brand_share,
    is_multisource,
    is_single_brand_equivalent,
    has_brand_version,
    has_generic_version

from {{ ref('int_part_d__drug_reference') }}
