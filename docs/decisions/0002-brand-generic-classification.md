# 0002: Name-based brand/generic classification

**Status:** Accepted

## Context

The drug-level Part D file gives `Brnd_Name` and `Gnrc_Name` but no explicit
brand/generic flag. The prescriber-level file has CMS's own brand/generic
claim totals, but they cannot be broken down by drug, and the savings estimate
needs drug-level detail. An NDC-level product file (e.g. FDA's Orange Book
multi-source codes) would need an NDC crosswalk that the public Part D files
do not carry.

## Decision

A row is generic when the normalized brand name (upper-case, punctuation
collapsed) equals the normalized generic name, or starts with it followed by a
formulation suffix (`METFORMIN HCL ER`, `ALBUTEROL SULFATE HFA`). Any other row
is brand-name, so branded generics count as brand.

**Revision after the first real run.** The first version counted every
mismatch as brand, which classified suffixed generics (Metformin Hcl Er, 17M
fills in 2021) as brand. Against CMS's own split, the revised rule's mean brand
share is 18.2% vs CMS 17.7% (old rule: 22.0%), with a prescriber-level
correlation of 0.74 (old: 0.72).

## Validation

`analyses/brand_share_vs_cms_classification.sql` compares each prescriber's
name-based brand share with the CMS classification by specialty (correlation
and mean absolute difference). Review it after every real run.

## Consequences

- Branded generics count as brand. They are also priced above plain generics,
  so the savings logic stays coherent.
- A brand whose trade name equals the generic name would be misclassified as
  generic. That is rare, and it biases the brand gap towards zero.
