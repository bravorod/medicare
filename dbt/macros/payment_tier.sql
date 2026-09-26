{#-
    Bucket a USD amount into the tiers set by var('payment_tier_breaks').
    With the default breaks [100, 1000, 10000] this yields:
      '0: none', '1: $1-99', '2: $100-999', '3: $1,000-9,999', '4: $10,000+'
-#}
{% macro payment_tier(amount_column) -%}
    {%- set breaks = var('payment_tier_breaks') -%}
    case
        when coalesce({{ amount_column }}, 0) <= 0 then '0: none'
        {%- for b in breaks %}
        {%- set lower = 1 if loop.first else breaks[loop.index0 - 1] %}
        when {{ amount_column }} < {{ b }} then '{{ loop.index }}: ${{ "{:,}".format(lower) }}-{{ "{:,}".format(b - 1) }}'
        {%- endfor %}
        else '{{ breaks | length + 1 }}: ${{ "{:,}".format(breaks[-1]) }}+'
    end
{%- endmacro %}
