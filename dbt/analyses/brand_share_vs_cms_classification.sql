-- Validation of the name-based brand/generic classification.
--
-- CMS's prescriber-level file carries its own brand/generic claim split. If
-- the brand_name != generic_name rule is sound, the two brand shares should
-- agree closely prescriber by prescriber. Run with `dbt compile` and paste the
-- SQL into the BigQuery console, or execute via the notebooks.
select
    prescriber_specialty,
    count(*)                                                        as n_prescribers,
    avg(brand_fill_share)                                           as avg_brand_share_name_rule,
    avg(cms_brand_claim_share)                                      as avg_brand_share_cms,
    corr(brand_fill_share, cms_brand_claim_share)                   as correlation,
    avg(abs(brand_fill_share - cms_brand_claim_share))              as mean_abs_difference
from {{ ref('fct_prescribers') }}
where in_cohort
  and cms_brand_claim_share is not null
group by prescriber_specialty
order by n_prescribers desc
