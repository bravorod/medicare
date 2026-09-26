{{ config(tags=['post_ml'], schema='reporting') }}

{#
    Where the top 1% of outlier scores sit, by specialty and by state, and how
    many later exclusions each segment's top 1% captured.
#}

with risk as (

    select * from {{ ref('fct_prescriber_risk') }}

),

{%- for dim in ['prescriber_specialty', 'prescriber_state'] %}
by_{{ dim }} as (

    select
        '{{ dim }}'                                                             as dimension,
        {{ dim }}                                                               as dimension_value,
        count(*)                                                                as n_prescribers,
        sum(case when is_top_1pct then 1 else 0 end)                            as n_top_1pct,
        sum(case when excluded_in_window then 1 else 0 end)                     as n_later_exclusions,
        sum(case when excluded_in_window and is_top_1pct then 1 else 0 end)     as n_exclusions_in_top_1pct
    from risk
    group by {{ dim }}

){{ ',' if not loop.last }}
{%- endfor %}

select
    *,
    {{ safe_divide('n_top_1pct', 'n_prescribers') }}                            as share_top_1pct
from (
    select * from by_prescriber_specialty
    union all
    select * from by_prescriber_state
) as stacked
