-- Every prescriber in fct_prescribers is counted in exactly one cohort-flow step.
select
    (select sum(n_prescribers) from {{ ref('rpt_cohort_flow') }})   as flow_total,
    (select count(*) from {{ ref('fct_prescribers') }})             as fact_total
from (select 1 as one) as dummy
where (select sum(n_prescribers) from {{ ref('rpt_cohort_flow') }})
   != (select count(*) from {{ ref('fct_prescribers') }})
