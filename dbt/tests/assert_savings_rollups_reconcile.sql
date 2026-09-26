-- Savings by drug (headline set) and the one-row summary must add up to the same total.
with by_drug as (
    select sum(estimated_savings_usd) as total
    from {{ ref('rpt_savings_by_drug') }}
    where is_single_brand_equivalent
),
summary as (
    select estimated_savings_usd as total from {{ ref('rpt_savings_summary') }}
)
select by_drug.total as by_drug_total, summary.total as summary_total
from by_drug
cross join summary
where abs(coalesce(by_drug.total, 0) - coalesce(summary.total, 0)) > 0.01
