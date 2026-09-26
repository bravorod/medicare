{#
    Row counts of every raw source table, used for the "records processed"
    headline and the data-sources section of the README.
#}

{%- set tables = [
    'part_d_prescriber_drug',
    'part_d_prescriber',
    'open_payments_general',
    'leie_exclusions',
    'nppes_providers',
] %}

{%- for table in tables %}
select
    '{{ table }}'                   as raw_table,
    count(*)                        as row_count
from {{ source('raw', table) }}
{{ 'union all' if not loop.last }}
{%- endfor %}
