{{ config(tags=['post_ml']) }}

{#
    Cohort prescribers with their outlier score attached. Internal use only:
    contains NPIs. Tableau extracts use the aggregated rpt_ models instead.
#}

select
    prescribers.*,
    scores.outlier_score,
    scores.outlier_percentile,
    scores.is_top_1pct,
    scores.top_feature,
    scores.top_feature_z

from {{ ref('fct_prescribers') }} as prescribers
inner join {{ source('ml', 'outlier_scores') }} as scores
    on prescribers.npi = scores.npi
where prescribers.in_cohort
