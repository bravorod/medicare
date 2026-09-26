{#
    Later OIG exclusions among cohort prescribers, by year and theme.
#}

select
    extract(year from window_exclusion_date)                as exclusion_year,
    window_exclusion_theme                                  as exclusion_theme,
    count(*)                                                as n_prescribers,
    sum(case when is_industry_paid then 1 else 0 end)       as n_industry_paid,
    avg(days_to_window_exclusion)                           as avg_days_to_exclusion
from {{ ref('fct_prescribers') }}
where in_cohort
  and excluded_in_window
group by 1, 2
