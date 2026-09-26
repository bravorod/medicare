-- Payment dollars and records by nature of payment, with the analysis category.
select
    payments.nature_of_payment,
    coalesce(categories.payment_category, 'other')      as payment_category,
    count(*)                                            as n_records,
    sum(payments.payment_amount_usd)                    as total_usd,
    avg(payments.payment_amount_usd)                    as avg_usd
from {{ ref('stg_open_payments__general_payments') }} as payments
left join {{ ref('payment_nature_categories') }} as categories
    on lower(trim(payments.nature_of_payment)) = lower(trim(categories.nature_of_payment))
where payments.npi is not null
group by 1, 2
order by total_usd desc
