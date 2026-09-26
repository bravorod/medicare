-- How many Open Payments dollars can be tied to a Part D prescriber by NPI?
with payments as (
    select *
    from {{ ref('stg_open_payments__general_payments') }}
    where not is_teaching_hospital
),
prescribers as (
    select distinct npi from {{ ref('stg_part_d__prescriber') }}
)
select
    count(*)                                                                    as n_records,
    sum(case when payments.npi is not null then 1 else 0 end)                   as n_with_npi,
    sum(case when prescribers.npi is not null then 1 else 0 end)                as n_matched_to_part_d,
    sum(payment_amount_usd)                                                     as total_usd,
    sum(case when prescribers.npi is not null then payment_amount_usd else 0 end) as matched_usd
from payments
left join prescribers on payments.npi = prescribers.npi
