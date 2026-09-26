{#
    Where every raw table came from (URL, checksum, load time) and whether it
    is synthetic. The Python results step reads this before publishing any
    number.
#}

select
    source_name,
    raw_table,
    cast(row_count as {{ dbt.type_bigint() }})              as row_count,
    source_url,
    sha256,
    downloaded_at,
    loaded_at,
    cast(data_year as {{ dbt.type_bigint() }})              as data_year,
    cast(is_synthetic as {{ dbt.type_boolean() }})          as is_synthetic
from {{ source('raw', 'load_provenance') }}
