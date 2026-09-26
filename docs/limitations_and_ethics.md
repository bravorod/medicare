# Limitations and responsible use

## What the analysis can and cannot say

**Association, not causation.** Industry-paid prescribers writing more
brand-name fills than comparable peers is a descriptive finding. Manufacturers
choose whom to pay and may target prescribers who already use their products.
Peer adjustment removes differences explained by specialty, state and patient
mix. It does not remove that selection.

**Savings are potential and gross.** The savings estimate prices excess brand
fills at CMS gross drug cost, which is before confidential manufacturer
rebates, and it assumes every excess fill could switch to the generic.
`savings_sensitivity.csv` shows how the figure shrinks under rebates and
partial switching. Some brand use is clinically appropriate (narrow therapeutic
index drugs, patient intolerance), so the achievable figure is lower than the
headline.

**The outlier score is a triage signal, not an accusation.** LEIE exclusions
cover many causes, including licence actions, convictions, fraud and loan
defaults. Most high-scoring prescribers are never excluded. The score should
only be used to prioritise human review, never to take action on its own.

**Outcome limitations.**

- LEIE is a current list, so anyone excluded and then reinstated before the
  download is not counted.
- Exclusions can lag the underlying conduct by years, so recent behaviour is
  under-represented.
- Matching is by NPI only. Exclusions without an NPI are not counted.

**Measurement limitations.** Part D rows with fewer than 11 claims are
suppressed. Open Payments covers only reporting manufacturers and GPOs, and
recipients can dispute records (disputed records are kept and counted in
`n_disputed_records`). The brand/generic rule treats branded generics as brand.

## Handling identifiable information

The sources are public, but combining them produces lists of named clinicians
with risk scores. The project keeps those lists inside the warehouse:

- Tableau extracts are aggregated by state, specialty, tier or drug, and any
  row describing fewer than 11 prescribers is dropped (the CMS convention).
- The optional prescriber-level extract replaces the NPI with a salted SHA-256
  pseudonym (salt supplied at run time, never committed) and drops names.
- `fct_prescriber_risk` (NPIs + scores) is documented as internal-only in dbt.
- The integration test asserts that no Tableau extract contains an `npi` column.
- Names are never shown in the README, memo or figures.

Please do not publish individual prescribers' scores. If a finding about a
specific prescriber seems to warrant action, the right channel is the
[HHS-OIG hotline](https://oig.hhs.gov/fraud/report-fraud/), not public
disclosure.

## Synthetic data

`partd-risk synthetic` generates simulated data with planted relationships so
that CI can exercise the full pipeline. Synthetic loads are flagged in
`load_provenance`. The results step refuses to produce headline numbers from
them unless `--allow-synthetic` is passed, and even then it watermarks every
number and writes outside `reports/`.
