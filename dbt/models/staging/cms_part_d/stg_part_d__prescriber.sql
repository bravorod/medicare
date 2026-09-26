{#
    One row per prescriber NPI: utilization totals, CMS's own brand/generic
    claim split, opioid measures and beneficiary case-mix used as controls.
    Cells CMS suppresses for privacy (<11) arrive blank and become NULL.
#}

with source as (

    select * from {{ source('raw', 'part_d_prescriber') }}

),

typed as (

    select
        {{ clean_npi('prscrbr_npi') }}                          as npi,
        upper({{ nullif_blank('prscrbr_ent_cd') }})             as entity_code,
        {{ nullif_blank('prscrbr_last_org_name') }}             as prescriber_last_or_org_name,
        {{ nullif_blank('prscrbr_first_name') }}                as prescriber_first_name,
        {{ nullif_blank('prscrbr_crdntls') }}                   as prescriber_credentials,
        {{ nullif_blank('prscrbr_city') }}                      as prescriber_city,
        upper({{ nullif_blank('prscrbr_state_abrvtn') }})       as prescriber_state,
        substr({{ nullif_blank('prscrbr_zip5') }}, 1, 5)        as prescriber_zip5,
        {{ safe_cast('prscrbr_ruca', type_double()) }}          as ruca_code,
        {{ nullif_blank('prscrbr_type') }}                      as prescriber_specialty,

        {{ safe_cast_int('tot_clms') }}                         as total_claims,
        {{ safe_cast('tot_30day_fills', type_double()) }}       as total_30day_fills,
        {{ safe_cast('tot_drug_cst', type_double()) }}          as total_drug_cost,
        {{ safe_cast_int('tot_day_suply') }}                    as total_day_supply,
        {{ safe_cast_int('tot_benes') }}                        as total_beneficiaries,

        {{ safe_cast_int('brnd_tot_clms') }}                    as cms_brand_claims,
        {{ safe_cast('brnd_tot_drug_cst', type_double()) }}     as cms_brand_drug_cost,
        {{ safe_cast_int('gnrc_tot_clms') }}                    as cms_generic_claims,
        {{ safe_cast('gnrc_tot_drug_cst', type_double()) }}     as cms_generic_drug_cost,
        {{ safe_cast_int('othr_tot_clms') }}                    as cms_other_claims,
        {{ safe_cast_int('lis_tot_clms') }}                     as lis_claims,

        {{ safe_cast_int('opioid_tot_clms') }}                  as opioid_claims,
        {{ safe_cast_int('opioid_la_tot_clms') }}               as opioid_long_acting_claims,
        {{ safe_cast('opioid_prscrbr_rate', type_double()) }}   as cms_opioid_prescribing_rate,
        {{ safe_cast_int('antbtc_tot_clms') }}                  as antibiotic_claims,
        {{ safe_cast_int('antpsyct_ge65_tot_clms') }}           as antipsychotic_ge65_claims,

        {{ safe_cast('bene_avg_age', type_double()) }}          as bene_avg_age,
        {{ safe_cast_int('bene_dual_cnt') }}                    as bene_dual_count,
        {{ safe_cast_int('bene_ndual_cnt') }}                   as bene_nondual_count,
        {{ safe_cast_int('bene_feml_cnt') }}                    as bene_female_count,
        {{ safe_cast_int('bene_male_cnt') }}                    as bene_male_count,
        {{ safe_cast('bene_avg_risk_scre', type_double()) }}    as bene_avg_risk_score

    from source

)

select
    *,
    ruca_code >= 4                                          as is_rural,
    {{ var('data_year') }}                                  as data_year
from typed
where npi is not null
