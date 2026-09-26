{#
    Generic-substitution savings from industry-paid prescribers, at
    specialty x generic-drug grain (multi-source drugs only).

    For each multi-source drug, expected brand fills for paid prescribers are
    their fills of that drug x the brand share among UNPAID prescribers of the
    same specialty (national unpaid share when the specialty has fewer than
    var('min_reference_peers') unpaid prescribers of the drug).

    Net excess = observed - expected brand fills, kept SIGNED and never
    floored: cells where paid prescribers wrote fewer brand fills than their
    peers offset cells where they wrote more. Flooring cells at zero would sum
    only the positive half of the noise and inflate the estimate (see ADR
    0005). Net excess is priced at the national brand-minus-generic gross cost
    per 30-day fill.

    This is gross Part D drug cost (before manufacturer rebates). Rebate and
    realization sensitivities are applied in Python
    (partd_risk.reporting.headline).
#}

{%- set min_ref = var('min_reference_peers') %}

with cohort as (

    select npi, prescriber_specialty, is_industry_paid
    from {{ ref('fct_prescribers') }}
    where in_cohort

),

drugs as (

    select
        generic_name_key,
        generic_name,
        example_brand_name,
        n_brand_products,
        is_single_brand_equivalent,
        brand_cost_per_fill,
        generic_cost_per_fill,
        brand_premium_per_fill
    from {{ ref('int_part_d__drug_reference') }}
    where is_multisource

),

npi_drug as (

    select
        fills.npi,
        cohort.prescriber_specialty,
        cohort.is_industry_paid,
        fills.generic_name_key,
        sum(case when fills.is_brand then fills.total_30day_fills else 0 end)  as brand_fills,
        sum(fills.total_30day_fills)                                            as total_fills

    from {{ ref('stg_part_d__prescriber_drug') }} as fills
    inner join cohort
        on fills.npi = cohort.npi
    inner join drugs
        on fills.generic_name_key = drugs.generic_name_key
    group by fills.npi, cohort.prescriber_specialty, cohort.is_industry_paid, fills.generic_name_key

),

ref_specialty as (

    select
        prescriber_specialty,
        generic_name_key,
        count(*)                                                        as n_ref,
        {{ safe_divide('sum(brand_fills)', 'sum(total_fills)') }}       as brand_share
    from npi_drug
    where not is_industry_paid
    group by prescriber_specialty, generic_name_key

),

ref_national as (

    select
        generic_name_key,
        count(*)                                                        as n_ref,
        {{ safe_divide('sum(brand_fills)', 'sum(total_fills)') }}       as brand_share
    from npi_drug
    where not is_industry_paid
    group by generic_name_key

),

paid as (

    select
        npi_drug.*,
        case
            when coalesce(rs.n_ref, 0) >= {{ min_ref }} then 'specialty_national'
            else 'all_prescribers'
        end                                                             as reference_level,
        case
            when coalesce(rs.n_ref, 0) >= {{ min_ref }} then rs.brand_share
            else rn.brand_share
        end                                                             as reference_brand_share

    from npi_drug
    left join ref_specialty as rs
        on npi_drug.prescriber_specialty = rs.prescriber_specialty
       and npi_drug.generic_name_key = rs.generic_name_key
    left join ref_national as rn
        on npi_drug.generic_name_key = rn.generic_name_key
    where npi_drug.is_industry_paid

),

cells as (

    select
        prescriber_specialty,
        generic_name_key,
        reference_level,
        min(reference_brand_share)                                      as reference_brand_share,
        count(*)                                                        as n_paid_prescribers,
        sum(total_fills)                                                as paid_total_fills,
        sum(brand_fills)                                                as observed_brand_fills,
        sum(total_fills * reference_brand_share)                        as expected_brand_fills

    from paid
    where reference_brand_share is not null
    group by prescriber_specialty, generic_name_key, reference_level

)

select
    {{ dbt_utils.generate_surrogate_key(['cells.prescriber_specialty', 'cells.generic_name_key']) }}
                                                                        as savings_cell_id,
    cells.prescriber_specialty,
    cells.generic_name_key,
    drugs.generic_name,
    drugs.example_brand_name,
    drugs.n_brand_products,
    drugs.is_single_brand_equivalent,
    cells.reference_level,
    cells.reference_brand_share,
    cells.n_paid_prescribers,
    cells.paid_total_fills,
    cells.observed_brand_fills,
    cells.expected_brand_fills,
    {{ safe_divide('cells.observed_brand_fills', 'cells.paid_total_fills') }}
                                                                        as observed_brand_share,
    cells.observed_brand_fills - cells.expected_brand_fills             as net_excess_brand_fills,
    drugs.brand_cost_per_fill,
    drugs.generic_cost_per_fill,
    drugs.brand_premium_per_fill,
    (cells.observed_brand_fills - cells.expected_brand_fills)
        * coalesce(drugs.brand_premium_per_fill, 0)                     as estimated_savings_usd

from cells
inner join drugs
    on cells.generic_name_key = drugs.generic_name_key
