{#
    Source-cleaning helpers shared by the staging models.
#}

{#- Empty or whitespace-only strings become NULL. -#}
{% macro nullif_blank(column) -%}
    nullif(trim({{ column }}), '')
{%- endmacro %}


{#-
    A valid NPI is exactly 10 digits. LEIE uses 0000000000 for "no NPI", and
    Open Payments leaves the field blank for teaching hospitals.
-#}
{% macro clean_npi(column) -%}
    case
        when {{ regexp_full_match('trim(' ~ column ~ ')', '[0-9]{10}') }}
            and trim({{ column }}) != '0000000000'
            then trim({{ column }})
    end
{%- endmacro %}


{#-
    Canonical drug-name key used to compare brand and generic names:
    upper-case, punctuation collapsed to single spaces, trimmed.
    "Metformin HCl ER" and "METFORMIN HCL  ER." both -> "METFORMIN HCL ER".
-#}
{% macro normalize_drug_name(column) -%}
    trim({{ regexp_replace_all('upper(' ~ column ~ ')', '[^A-Z0-9]+', ' ') }})
{%- endmacro %}


{#- First day of the outcome window: Jan 1 of the year after the data year. -#}
{% macro outcome_window_start() -%}
    {{ date_literal((var('data_year') | int + 1) ~ '-01-01') }}
{%- endmacro %}


{#- Last day of the data year. -#}
{% macro data_year_end() -%}
    {{ date_literal(var('data_year') ~ '-12-31') }}
{%- endmacro %}
