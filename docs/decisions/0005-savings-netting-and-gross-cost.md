# 0005: Savings: signed net excess, single-brand equivalents, gross cost

**Status:** Accepted (revised after the first real run)

## Context

The savings headline must not be inflated by noise, by comparing different
products, or by pricing that ignores rebates.

## Decision

- **Multi-source drugs only:** a generic version was dispensed nationally.
- **Reference:** the expected brand share comes from **unpaid** prescribers of
  the same drug in the same specialty (national fallback below 10 unpaid
  prescribers).
- **Signed net excess, never floored.** The first design netted within each
  specialty x drug cell and floored cells at zero. On the 2021 data that gave
  about $661M, even though paid prescribers' multi-source brand fills matched
  expected almost exactly in aggregate: 18,094 cells, and summing only the
  positive ones reproduced the noise bias the netting was meant to remove.
  Cells are now summed with their sign.
- **Headline on single-brand equivalents.** CMS pools dosage forms under one
  generic name, so a generic name with several brand products (Pennsaid vs
  diclofenac tablets, Duopa vs levodopa tablets, Abilify Maintena vs
  aripiprazole tablets) prices different products against each other. The
  headline keeps generic names with exactly one brand product, which in 2021
  cover about half of paid prescribers' multi-source fills. All multi-source
  drugs are reported as an upper bound.
- **Priced** at the national gross brand-minus-generic cost per 30-day fill,
  with a sensitivity table for 15% / 30% brand rebates and 50% switching.

## Consequences

The headline is a conservative estimate of *potential* gross savings on
like-for-like substitutions. It excludes real but formulation-confounded
opportunities, which appear only in the upper bound.
