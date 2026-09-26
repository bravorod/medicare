{#
    One row per Open Payments general payment record.

    Up to five products can be attached to a payment. A payment counts as
    drug-related when any attached product is a drug or biological.
#}

with source as (

    select * from {{ source('raw', 'open_payments_general') }}

),

typed as (

    select
        {{ nullif_blank('record_id') }}                                         as payment_record_id,
        {{ clean_npi('covered_recipient_npi') }}                                as npi,
        {{ nullif_blank('covered_recipient_profile_id') }}                      as recipient_profile_id,
        {{ nullif_blank('covered_recipient_type') }}                            as recipient_type,
        upper({{ nullif_blank('recipient_state') }})                            as recipient_state,
        {{ nullif_blank('covered_recipient_primary_type_1') }}                  as recipient_primary_type,
        {{ nullif_blank('covered_recipient_specialty_1') }}                     as recipient_specialty,
        {{ nullif_blank('applicable_manufacturer_or_applicable_gpo_making_payment_id') }}
                                                                                as manufacturer_id,
        {{ nullif_blank('applicable_manufacturer_or_applicable_gpo_making_payment_name') }}
                                                                                as manufacturer_name,
        {{ safe_cast('total_amount_of_payment_usdollars', type_double()) }}     as payment_amount_usd,
        {{ parse_date_safe(nullif_blank('date_of_payment'), '%m/%d/%Y') }}      as payment_date,
        {{ safe_cast_int('number_of_payments_included_in_total_amount') }}      as number_of_payments,
        {{ nullif_blank('form_of_payment_or_transfer_of_value') }}              as form_of_payment,
        {{ nullif_blank('nature_of_payment_or_transfer_of_value') }}            as nature_of_payment,
        lower({{ nullif_blank('related_product_indicator') }})                  as related_product_indicator,
        {%- for i in range(1, 6) %}
        lower({{ nullif_blank('indicate_drug_or_biological_or_device_or_medical_supply_' ~ i) }})
                                                                                as product_type_{{ i }},
        {{ nullif_blank('name_of_drug_or_biological_or_device_or_medical_supply_' ~ i) }}
                                                                                as product_name_{{ i }},
        {%- endfor %}
        {{ safe_cast_int('program_year') }}                                     as program_year,
        coalesce(lower({{ nullif_blank('dispute_status_for_publication') }}) = 'yes', false)
                                                                                as is_disputed

    from source

)

select
    *,
    (
        {%- for i in range(1, 6) %}
        coalesce(product_type_{{ i }} in ('drug', 'biological'), false){{ ' or' if not loop.last }}
        {%- endfor %}
    )                                                                           as is_drug_related,
    coalesce(lower(recipient_type) like '%teaching hospital%', false)           as is_teaching_hospital
from typed
where payment_record_id is not null
