{#
    Industry general payments received by each NPI in the program year that
    matches the Part D data year, split by nature-of-payment category.
#}

{%- set categories = var('payment_categories') %}

with payments as (

    select * from {{ ref('stg_open_payments__general_payments') }}
    where npi is not null
      and not is_teaching_hospital
      and coalesce(program_year, {{ var('data_year') }}) = {{ var('data_year') }}

),

categories as (

    select
        lower(trim(nature_of_payment)) as nature_key,
        payment_category
    from {{ ref('payment_nature_categories') }}

),

categorized as (

    select
        payments.*,
        coalesce(categories.payment_category, 'other') as payment_category

    from payments
    left join categories
        on lower(trim(payments.nature_of_payment)) = categories.nature_key

)

select
    npi,
    count(*)                                                                    as n_payment_records,
    sum(coalesce(number_of_payments, 1))                                        as n_payments,
    count(distinct manufacturer_id)                                             as n_manufacturers,
    sum(payment_amount_usd)                                                     as total_payment_usd,
    max(payment_amount_usd)                                                     as max_single_payment_usd,
    sum(case when is_drug_related then 1 else 0 end)                            as n_drug_related_records,
    sum(case when is_drug_related then payment_amount_usd else 0 end)           as drug_related_payment_usd,
    count(distinct case when is_drug_related then manufacturer_id end)          as n_drug_manufacturers,
    {%- for category in categories %}
    sum(case when payment_category = '{{ category }}' then payment_amount_usd else 0 end)
                                                                                as {{ category }}_usd,
    {%- endfor %}
    sum(case when is_disputed then 1 else 0 end)                                as n_disputed_records,
    min(payment_date)                                                           as first_payment_date,
    max(payment_date)                                                           as last_payment_date

from categorized
group by npi
