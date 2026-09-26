{#
    One row per prescriber x (brand name, generic name) for the data year.

    Brand vs generic: CMS publishes the brand name and the generic name on
    every row. A row is a generic product when the normalized brand name equals
    the generic name, or is the generic name plus a formulation suffix
    ("Metformin Hcl Er", "Albuterol Sulfate Hfa"). Anything else is a
    brand-name (or branded-generic) product. See
    docs/decisions/0002-brand-generic-classification.md.
#}

with source as (

    select * from {{ source('raw', 'part_d_prescriber_drug') }}

),

typed as (

    select
        {{ clean_npi('prscrbr_npi') }}                          as npi,
        {{ nullif_blank('prscrbr_last_org_name') }}             as prescriber_last_or_org_name,
        {{ nullif_blank('prscrbr_first_name') }}                as prescriber_first_name,
        {{ nullif_blank('prscrbr_city') }}                      as prescriber_city,
        upper({{ nullif_blank('prscrbr_state_abrvtn') }})       as prescriber_state,
        {{ nullif_blank('prscrbr_type') }}                      as prescriber_specialty,
        {{ nullif_blank('prscrbr_type_src') }}                  as prescriber_specialty_source,
        {{ nullif_blank('brnd_name') }}                         as brand_name,
        {{ nullif_blank('gnrc_name') }}                         as generic_name,
        {{ normalize_drug_name('brnd_name') }}                  as brand_name_key,
        {{ normalize_drug_name('gnrc_name') }}                  as generic_name_key,
        {{ safe_cast_int('tot_clms') }}                         as total_claims,
        {{ safe_cast('tot_30day_fills', type_double()) }}       as total_30day_fills,
        {{ safe_cast_int('tot_day_suply') }}                    as total_day_supply,
        {{ safe_cast('tot_drug_cst', type_double()) }}          as total_drug_cost,
        {{ safe_cast_int('tot_benes') }}                        as total_beneficiaries

    from source

)

select
    {{ dbt_utils.generate_surrogate_key(['npi', 'brand_name_key', 'generic_name_key']) }}
        as prescriber_drug_id,
    npi,
    prescriber_last_or_org_name,
    prescriber_first_name,
    prescriber_city,
    prescriber_state,
    prescriber_specialty,
    prescriber_specialty_source,
    brand_name,
    generic_name,
    brand_name_key,
    generic_name_key,
    coalesce(
        brand_name_key != generic_name_key
        and not starts_with(brand_name_key, generic_name_key || ' '),
        false
    )                                                       as is_brand,
    total_claims,
    coalesce(total_30day_fills, 0)                          as total_30day_fills,
    total_day_supply,
    coalesce(total_drug_cost, 0)                            as total_drug_cost,
    total_beneficiaries,
    {{ var('data_year') }}                                  as data_year

from typed
where npi is not null
  and generic_name_key is not null
