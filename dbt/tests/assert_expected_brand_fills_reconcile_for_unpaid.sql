-- By construction, unpaid prescribers whose reference is their own
-- specialty x state cell have observed == expected brand fills in aggregate.
select
    prescriber_specialty,
    prescriber_state,
    sum(brand_fills)            as observed,
    sum(expected_brand_fills)   as expected
from {{ ref('mart_brand_peer_comparison') }}
where not is_industry_paid
  and reference_level = 'specialty_state'
group by prescriber_specialty, prescriber_state
having abs(sum(brand_fills) - sum(expected_brand_fills)) > 0.01 * greatest(sum(brand_fills), 1)
