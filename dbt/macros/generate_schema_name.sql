{#
    Keep dbt's default "<target schema>_<custom schema>" naming in every
    environment so BigQuery datasets read partd_risk_staging,
    partd_risk_marts, ... and the Python layer can find them predictably.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ default_schema }}_{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
