{#
    CONSORT-style cohort flow: how many prescribers each rule removes.
#}

with prescribers as (

    select cohort_exclusion_reason
    from {{ ref('fct_prescribers') }}

),

counts as (

    select
        coalesce(cohort_exclusion_reason, '5_analysis_cohort')              as step,
        count(*)                                                            as n_prescribers
    from prescribers
    group by 1

)

select
    step,
    case step
        when '1_not_individual' then 'Removed: organization, not an individual prescriber'
        when '2_missing_specialty_or_state' then 'Removed: specialty or state missing'
        when '3_below_min_fills' then 'Removed: fewer than {{ var("min_total_fills") }} 30-day fills'
        when '4_excluded_before_window' then 'Removed: already excluded by OIG by end of {{ var("data_year") }}'
        when '5_analysis_cohort' then 'Analysis cohort'
    end                                                                     as description,
    n_prescribers,
    (select count(*) from prescribers)
        - sum(n_prescribers) over (order by step rows between unbounded preceding and current row)
        + case when step = '5_analysis_cohort' then n_prescribers else 0 end
                                                                            as remaining_after_step
from counts
