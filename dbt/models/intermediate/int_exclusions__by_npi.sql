{#
    OIG exclusion history per NPI relative to the data year.

    * excluded_before_window: excluded on or before the end of the data year.
      These prescribers are removed from the analysis cohort.
    * excluded_in_window: first exclusion falls in the outcome window
      (from Jan 1 of the following year through the LEIE snapshot date, or
      var('outcome_window_end') when set). This is the validation outcome for
      the outlier score; it is never used to fit the score.
#}

with exclusions as (

    select * from {{ ref('stg_leie__exclusions') }}
    where npi is not null
      and exclusion_date is not null

),

types as (

    select exclusion_type_code, authority, exclusion_theme, description
    from {{ ref('leie_exclusion_types') }}

),

typed as (

    select
        exclusions.*,
        types.authority,
        coalesce(types.exclusion_theme, 'unmapped')     as exclusion_theme,
        types.description                               as exclusion_description

    from exclusions
    left join types
        on exclusions.exclusion_type_code = types.exclusion_type_code

),

window_bounds as (

    select
        {{ outcome_window_start() }} as window_start,
        {%- if var('outcome_window_end') %}
        {{ date_literal(var('outcome_window_end')) }} as window_end
        {%- else %}
        (select max(exclusion_date) from exclusions) as window_end
        {%- endif %}

),

first_in_window as (

    select
        typed.npi,
        typed.exclusion_date,
        typed.exclusion_type_code,
        typed.exclusion_theme,
        typed.authority

    from typed
    cross join window_bounds
    where typed.exclusion_date between window_bounds.window_start and window_bounds.window_end
    qualify row_number() over (
        partition by typed.npi order by typed.exclusion_date, typed.exclusion_id
    ) = 1

),

per_npi as (

    select
        typed.npi,
        count(*)                                                                    as n_exclusion_records,
        min(typed.exclusion_date)                                                   as first_exclusion_date,
        max(case when typed.exclusion_date <= {{ data_year_end() }} then 1 else 0 end) = 1
                                                                                    as excluded_before_window

    from typed
    group by typed.npi

)

select
    per_npi.npi,
    per_npi.n_exclusion_records,
    per_npi.first_exclusion_date,
    per_npi.excluded_before_window,
    first_in_window.npi is not null and not per_npi.excluded_before_window          as excluded_in_window,
    first_in_window.exclusion_date                                                  as window_exclusion_date,
    first_in_window.exclusion_type_code                                             as window_exclusion_type_code,
    first_in_window.exclusion_theme                                                 as window_exclusion_theme,
    first_in_window.authority                                                       as window_exclusion_authority,
    {{ dbt.datediff(data_year_end(), 'first_in_window.exclusion_date', 'day') }}    as days_to_window_exclusion,
    window_bounds.window_start,
    window_bounds.window_end

from per_npi
cross join window_bounds
left join first_in_window
    on per_npi.npi = first_in_window.npi
