{{ config(tags=['post_ml'], schema='reporting') }}

{#
    Which feature drives the score for prescribers in the top 1%, overall and
    for those later excluded.
#}

select
    top_feature,
    count(*)                                                            as n_top_1pct,
    sum(case when excluded_in_window then 1 else 0 end)                 as n_later_excluded,
    avg(top_feature_z)                                                  as avg_top_feature_z
from {{ ref('fct_prescriber_risk') }}
where is_top_1pct
group by top_feature
