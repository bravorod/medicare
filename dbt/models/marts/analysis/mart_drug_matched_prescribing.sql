{#
    Drug-matched analysis: do prescribers paid in connection with a specific
    brand write more of THAT brand than same-specialty peers who were not?

    For each brand b and specialty s:
        unpaid rate r(s,b) = brand-b fills / all fills among cohort prescribers
                             in s who received no payment naming b
        expected(paid)     = all fills of paid-for-b prescribers in s x r(s,b)
    Aggregated over specialties to an observed / expected ratio per brand.
    Brands named in payments to fewer than 25 cohort prescribers are dropped.
#}

with cohort as (

    select npi, prescriber_specialty, drug_detail_fills
    from {{ ref('fct_prescribers') }}
    where in_cohort

),

brand_fills as (

    select
        npi,
        brand_name_key,
        min(brand_name)                     as brand_name,
        sum(total_30day_fills)              as fills
    from {{ ref('stg_part_d__prescriber_drug') }}
    where is_brand
    group by npi, brand_name_key

),

paid_for as (

    select matched.npi, matched.brand_name_key, matched.payment_usd
    from {{ ref('int_payments__drug_matched') }} as matched
    inner join cohort on matched.npi = cohort.npi

),

specialty_totals as (

    select prescriber_specialty, sum(drug_detail_fills) as all_fills
    from cohort
    group by prescriber_specialty

),

brand_by_specialty as (

    select
        cohort.prescriber_specialty,
        brand_fills.brand_name_key,
        min(brand_fills.brand_name)         as brand_name,
        sum(brand_fills.fills)              as brand_fills
    from brand_fills
    inner join cohort on brand_fills.npi = cohort.npi
    group by cohort.prescriber_specialty, brand_fills.brand_name_key

),

paid_by_specialty as (

    select
        cohort.prescriber_specialty,
        paid_for.brand_name_key,
        count(*)                                    as n_paid_prescribers,
        sum(paid_for.payment_usd)                   as payment_usd,
        sum(cohort.drug_detail_fills)               as paid_all_fills,
        sum(coalesce(brand_fills.fills, 0))         as paid_brand_fills
    from paid_for
    inner join cohort on paid_for.npi = cohort.npi
    left join brand_fills
        on paid_for.npi = brand_fills.npi
       and paid_for.brand_name_key = brand_fills.brand_name_key
    group by cohort.prescriber_specialty, paid_for.brand_name_key

),

cells as (

    select
        paid.prescriber_specialty,
        paid.brand_name_key,
        brand.brand_name,
        paid.n_paid_prescribers,
        paid.payment_usd,
        paid.paid_brand_fills,
        paid.paid_all_fills,
        {{ safe_divide(
            'coalesce(brand.brand_fills, 0) - paid.paid_brand_fills',
            'totals.all_fills - paid.paid_all_fills'
        ) }}                                        as unpaid_rate

    from paid_by_specialty as paid
    inner join specialty_totals as totals
        on paid.prescriber_specialty = totals.prescriber_specialty
    left join brand_by_specialty as brand
        on paid.prescriber_specialty = brand.prescriber_specialty
       and paid.brand_name_key = brand.brand_name_key

),

by_brand as (

    select
        brand_name_key,
        min(brand_name)                             as brand_name,
        sum(n_paid_prescribers)                     as n_paid_prescribers,
        sum(payment_usd)                            as payment_usd,
        sum(paid_brand_fills)                       as observed_brand_fills,
        sum(paid_all_fills * unpaid_rate)           as expected_brand_fills
    from cells
    where unpaid_rate is not null
    group by brand_name_key

)

select
    *,
    {{ safe_divide('observed_brand_fills', 'expected_brand_fills') }}   as oe_ratio
from by_brand
where n_paid_prescribers >= 25
  and brand_name is not null
