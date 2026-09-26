{#
    NPI x brand-name pairs where the prescriber received a payment that named
    that product. Used to test whether prescribers write more of the specific
    brand they were paid in connection with (docs/methodology.md, section 3.4).
#}

with payments as (

    select * from {{ ref('stg_open_payments__general_payments') }}
    where npi is not null
      and not is_teaching_hospital
      and coalesce(program_year, {{ var('data_year') }}) = {{ var('data_year') }}

),

product_lines as (

    {%- for i in range(1, 6) %}
    select
        npi,
        payment_record_id,
        payment_amount_usd,
        manufacturer_id,
        {{ normalize_drug_name('product_name_' ~ i) }} as product_name_key
    from payments
    where product_type_{{ i }} in ('drug', 'biological')
      and product_name_{{ i }} is not null
    {{ 'union all' if not loop.last }}
    {%- endfor %}

)

select
    npi,
    product_name_key                        as brand_name_key,
    count(distinct payment_record_id)       as n_payment_records,
    sum(payment_amount_usd)                 as payment_usd,
    count(distinct manufacturer_id)         as n_manufacturers

from product_lines
where product_name_key != ''
group by npi, product_name_key
