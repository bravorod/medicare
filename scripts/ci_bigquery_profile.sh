#!/usr/bin/env bash
# Write a throwaway BigQuery profile so `dbt compile` can render the BigQuery
# dialect in CI. The key is generated on the fly, belongs to no real account
# and is never used to execute anything.
set -euo pipefail
dir="${1:-.ci-bq-profile}"
mkdir -p "$dir"
openssl genrsa -out "$dir/key.pem" 2048 2>/dev/null
python - "$dir" <<'PY'
import json, pathlib, sys
d = pathlib.Path(sys.argv[1]).resolve()
json.dump({
    "type": "service_account", "project_id": "ci-compile-only", "private_key_id": "ci",
    "private_key": (d / "key.pem").read_text(), "client_email": "ci@ci-compile-only.iam.gserviceaccount.com",
    "client_id": "0", "token_uri": "https://oauth2.googleapis.com/token",
}, open(d / "sa.json", "w"))
(d / "profiles.yml").write_text(f"""partd_risk:
  target: bigquery
  outputs:
    bigquery:
      type: bigquery
      method: service-account
      keyfile: {d / 'sa.json'}
      project: ci-compile-only
      dataset: partd_risk
      location: US
      threads: 4
""")
PY
echo "$dir"
