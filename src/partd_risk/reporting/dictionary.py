"""Generate docs/data_dictionary.md from the dbt model property files."""

from __future__ import annotations

from pathlib import Path

import yaml

LAYER_ORDER = ["staging", "intermediate", "marts", "reporting", "post_ml"]


def _clean(text: str | None) -> str:
    return " ".join((text or "").split()).replace("|", "\\|")


def collect_models(models_dir: Path) -> list[dict]:
    models = []
    for path in sorted(models_dir.rglob("*.yml")):
        spec = yaml.safe_load(path.read_text()) or {}
        layer = path.relative_to(models_dir).parts[0]
        for model in spec.get("models", []):
            models.append({**model, "_layer": layer, "_path": path})
    order = {name: i for i, name in enumerate(LAYER_ORDER)}
    return sorted(models, key=lambda m: (order.get(m["_layer"], 99), m["name"]))


def render(models: list[dict]) -> str:
    lines = [
        "# Data dictionary",
        "",
        "Generated from the dbt model YAML by `partd-risk data-dictionary`; do not edit by hand.",
        "Run `dbt docs generate && dbt docs serve` for the full lineage graph.",
        "",
    ]
    current = None
    for model in models:
        if model["_layer"] != current:
            current = model["_layer"]
            lines += [f"## {current.replace('_', ' ').title()}", ""]
        lines += [f"### `{model['name']}`", "", _clean(model.get("description")), ""]
        columns = [c for c in model.get("columns", []) if c.get("description")]
        if columns:
            lines += ["| Column | Description |", "|---|---|"]
            lines += [f"| `{c['name']}` | {_clean(c['description'])} |" for c in columns]
            lines.append("")
    return "\n".join(lines)


def write_data_dictionary(models_dir: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(render(collect_models(models_dir)))
    return dest
