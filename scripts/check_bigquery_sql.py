"""Parse every dbt-compiled model with sqlglot's BigQuery dialect.

CI cannot talk to BigQuery, so it compiles the project for the bigquery target
(with a throwaway service-account key; nothing is executed) and then parses
the rendered SQL. This catches dialect mistakes in the cross-database macros,
such as a DuckDB-only function leaking into the BigQuery build.

    python scripts/check_bigquery_sql.py dbt/target_bq/compiled/partd_risk
"""

from __future__ import annotations

import sys
from pathlib import Path

import sqlglot

DUCKDB_ONLY = ("try_cast(", "try_strptime(", "regexp_full_match(", "::")


def main(root: str) -> int:
    files = sorted(Path(root).rglob("*.sql"))
    if not files:
        print(f"No compiled SQL under {root}", file=sys.stderr)
        return 1
    failures = 0
    for path in files:
        sql = path.read_text()
        problems = [token for token in DUCKDB_ONLY if token in sql.lower()]
        try:
            sqlglot.parse(sql, read="bigquery", error_level=sqlglot.ErrorLevel.RAISE)
        except sqlglot.errors.ParseError as exc:
            problems.append(str(exc).splitlines()[0])
        if problems:
            failures += 1
            print(f"FAIL {path.relative_to(root)}: {'; '.join(problems)}")
    print(f"{len(files) - failures}/{len(files)} compiled models parse as BigQuery SQL")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "dbt/target_bq/compiled/partd_risk"))
