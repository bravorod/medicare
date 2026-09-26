{#
    Cross-database helpers.

    Production runs on BigQuery; CI and local development run the exact same
    models on DuckDB. Anything dialect-specific goes through adapter.dispatch
    here so that model SQL stays portable.
#}

{# ---- types ------------------------------------------------------------- #}

{% macro type_double() -%}
    {{ return(adapter.dispatch('type_double', 'partd_risk')()) }}
{%- endmacro %}

{% macro bigquery__type_double() -%} float64 {%- endmacro %}
{% macro default__type_double() -%} double {%- endmacro %}


{# ---- casting ----------------------------------------------------------- #}

{% macro safe_cast(expr, type) -%}
    {{ return(adapter.dispatch('safe_cast', 'partd_risk')(expr, type)) }}
{%- endmacro %}

{% macro bigquery__safe_cast(expr, type) -%} safe_cast({{ expr }} as {{ type }}) {%- endmacro %}
{% macro duckdb__safe_cast(expr, type) -%} try_cast({{ expr }} as {{ type }}) {%- endmacro %}
{% macro default__safe_cast(expr, type) -%} cast({{ expr }} as {{ type }}) {%- endmacro %}


{#- Integers in CMS files sometimes arrive as "12.0"; go through double first. -#}
{% macro safe_cast_int(expr) -%}
    cast(round({{ safe_cast(expr, type_double()) }}) as {{ dbt.type_bigint() }})
{%- endmacro %}


{% macro safe_divide(numerator, denominator) -%}
    {{ return(adapter.dispatch('safe_divide', 'partd_risk')(numerator, denominator)) }}
{%- endmacro %}

{% macro bigquery__safe_divide(numerator, denominator) -%}
    safe_divide({{ numerator }}, {{ denominator }})
{%- endmacro %}

{% macro default__safe_divide(numerator, denominator) -%}
    (cast({{ numerator }} as {{ type_double() }}) / nullif({{ denominator }}, 0))
{%- endmacro %}


{# ---- dates ------------------------------------------------------------- #}

{#- Parse a string to DATE with a strftime-style format; NULL on failure. -#}
{% macro parse_date_safe(expr, fmt) -%}
    {{ return(adapter.dispatch('parse_date_safe', 'partd_risk')(expr, fmt)) }}
{%- endmacro %}

{% macro bigquery__parse_date_safe(expr, fmt) -%}
    safe.parse_date('{{ fmt }}', {{ expr }})
{%- endmacro %}

{% macro duckdb__parse_date_safe(expr, fmt) -%}
    cast(try_strptime({{ expr }}, '{{ fmt }}') as date)
{%- endmacro %}


{% macro date_literal(value) -%}
    cast('{{ value }}' as date)
{%- endmacro %}


{# ---- strings ----------------------------------------------------------- #}

{% macro regexp_replace_all(expr, pattern, replacement) -%}
    {{ return(adapter.dispatch('regexp_replace_all', 'partd_risk')(expr, pattern, replacement)) }}
{%- endmacro %}

{% macro bigquery__regexp_replace_all(expr, pattern, replacement) -%}
    regexp_replace({{ expr }}, r'{{ pattern }}', '{{ replacement }}')
{%- endmacro %}

{% macro duckdb__regexp_replace_all(expr, pattern, replacement) -%}
    regexp_replace({{ expr }}, '{{ pattern }}', '{{ replacement }}', 'g')
{%- endmacro %}


{% macro regexp_full_match(expr, pattern) -%}
    {{ return(adapter.dispatch('regexp_full_match', 'partd_risk')(expr, pattern)) }}
{%- endmacro %}

{% macro bigquery__regexp_full_match(expr, pattern) -%}
    regexp_contains({{ expr }}, r'^{{ pattern }}$')
{%- endmacro %}

{% macro duckdb__regexp_full_match(expr, pattern) -%}
    regexp_full_match({{ expr }}, '{{ pattern }}')
{%- endmacro %}


{# ---- math ------------------------------------------------------------- #}

{#- GREATEST that treats NULL as "no value" on every engine. -#}
{% macro greatest_not_null(a, b) -%}
    case
        when {{ a }} is null then {{ b }}
        when {{ b }} is null then {{ a }}
        when {{ a }} >= {{ b }} then {{ a }}
        else {{ b }}
    end
{%- endmacro %}
