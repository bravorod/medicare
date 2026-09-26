# 0006: Aggregate / pseudonymized reporting only

**Status:** Accepted

## Context

Joining public datasets produces named clinicians with risk scores. The
stakeholder deliverables (Tableau, memo, README) do not need identities.

## Decision

- Tableau extracts are aggregates (state, specialty, tier, drug), with rows
  describing fewer than 11 prescribers suppressed.
- The optional prescriber-level extract uses a salted SHA-256 pseudonym, has
  no names, and needs `TABLEAU_PSEUDONYM_SALT` at run time.
- NPI-level tables stay in the warehouse and are documented as internal.
- An integration test fails if any extract contains an `npi` column.

## Consequences

Drill-down to individuals happens only inside the warehouse, by people with
access to it.
