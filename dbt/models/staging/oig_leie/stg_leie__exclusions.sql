{#
    One row per OIG exclusion. LEIE encodes "no date" as 00000000 and "no NPI"
    as 0000000000; both become NULL here.
#}

with source as (

    select * from {{ source('raw', 'leie_exclusions') }}

),

typed as (

    select
        {{ clean_npi('npi') }}                                                  as npi,
        {{ nullif_blank('lastname') }}                                          as last_name,
        {{ nullif_blank('firstname') }}                                         as first_name,
        {{ nullif_blank('midname') }}                                           as middle_name,
        {{ nullif_blank('busname') }}                                           as business_name,
        {{ nullif_blank('general') }}                                           as general_category,
        {{ nullif_blank('specialty') }}                                         as specialty,
        {{ nullif_blank('city') }}                                              as city,
        upper({{ nullif_blank('state') }})                                      as state,
        lower(replace({{ nullif_blank('excltype') }}, ' ', ''))                 as exclusion_type_code,
        {{ parse_date_safe("nullif(trim(excldate), '00000000')", '%Y%m%d') }}   as exclusion_date,
        {{ parse_date_safe("nullif(trim(reindate), '00000000')", '%Y%m%d') }}   as reinstatement_date,
        {{ parse_date_safe("nullif(trim(waiverdate), '00000000')", '%Y%m%d') }} as waiver_date,
        {{ nullif_blank('wvrstate') }}                                          as waiver_state

    from source

)

select
    {{ dbt_utils.generate_surrogate_key([
        'npi', 'last_name', 'first_name', 'business_name', 'exclusion_type_code', 'exclusion_date', 'state'
    ]) }}                                                                       as exclusion_id,
    *,
    business_name is not null and last_name is null                             as is_entity
from typed
