{#
    One row per NPI from the NPPES registry snapshot. The primary taxonomy is
    the slot whose "primary taxonomy switch" is Y (falling back to slot 1).
#}

with source as (

    select * from {{ source('raw', 'nppes_providers') }}

),

typed as (

    select
        {{ clean_npi('npi') }}                                                  as npi,
        {{ safe_cast_int('entity_type_code') }}                                 as entity_type_code,
        {{ nullif_blank('provider_last_name_legal_name') }}                     as last_name,
        {{ nullif_blank('provider_first_name') }}                               as first_name,
        {{ nullif_blank('provider_credential_text') }}                          as credential_text,
        {{ nullif_blank('provider_business_practice_location_address_city_name') }}
                                                                                as practice_city,
        upper({{ nullif_blank('provider_business_practice_location_address_state_name') }})
                                                                                as practice_state,
        substr({{ nullif_blank('provider_business_practice_location_address_postal_code') }}, 1, 5)
                                                                                as practice_zip5,
        {{ parse_date_safe(nullif_blank('provider_enumeration_date'), '%m/%d/%Y') }}
                                                                                as enumeration_date,
        {{ parse_date_safe(nullif_blank('last_update_date'), '%m/%d/%Y') }}     as last_update_date,
        {{ nullif_blank('npi_deactivation_reason_code') }}                      as deactivation_reason_code,
        {{ parse_date_safe(nullif_blank('npi_deactivation_date'), '%m/%d/%Y') }}
                                                                                as deactivation_date,
        {{ parse_date_safe(nullif_blank('npi_reactivation_date'), '%m/%d/%Y') }}
                                                                                as reactivation_date,
        coalesce(upper({{ nullif_blank('is_sole_proprietor') }}) = 'Y', false)  as is_sole_proprietor,
        coalesce(
            {%- for i in range(1, 16) %}
            case
                when upper(trim(healthcare_provider_primary_taxonomy_switch_{{ i }})) = 'Y'
                    then {{ nullif_blank('healthcare_provider_taxonomy_code_' ~ i) }}
            end,
            {%- endfor %}
            {{ nullif_blank('healthcare_provider_taxonomy_code_1') }}
        )                                                                       as primary_taxonomy_code

    from source

)

select * from typed
where npi is not null
