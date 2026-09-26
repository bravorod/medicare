"""Synthetic raw data for tests and CI.

Generates small raw tables with *exactly* the column layout the real loader
produces (normalized header names, every value a string), so the whole dbt +
Python pipeline can be exercised end to end on DuckDB without downloading
anything.

Nothing produced here is a finding. Every load is stamped
``is_synthetic = true`` in ``load_provenance``, and the results step refuses
to publish headline numbers from a synthetic warehouse unless explicitly told
to (and then labels every number SYNTHETIC).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from partd_risk.config import PipelineConfig

log = logging.getLogger(__name__)

SPECIALTIES = {
    # specialty: (share of prescribers, baseline brand share, opioid share, prob. paid)
    "Internal Medicine": (0.22, 0.20, 0.04, 0.55),
    "Family Practice": (0.22, 0.18, 0.05, 0.50),
    "Nurse Practitioner": (0.18, 0.16, 0.05, 0.35),
    "Physician Assistant": (0.08, 0.15, 0.06, 0.30),
    "Cardiology": (0.09, 0.30, 0.01, 0.70),
    "Endocrinology": (0.06, 0.40, 0.01, 0.75),
    "Psychiatry": (0.08, 0.25, 0.01, 0.55),
    "Pain Management": (0.07, 0.22, 0.35, 0.65),
}
STATES = {"CA": 0.16, "TX": 0.13, "FL": 0.12, "NY": 0.11, "PA": 0.08, "OH": 0.08,
          "IL": 0.08, "GA": 0.08, "NC": 0.08, "MI": 0.08}  # fmt: skip

# (generic name, brand name, multi-source?, generic cost/fill, brand cost/fill, class)
DRUGS = [
    ("Atorvastatin Calcium", "Lipitor", True, 9.0, 310.0, "cardio"),
    ("Rosuvastatin Calcium", "Crestor", True, 11.0, 290.0, "cardio"),
    ("Amlodipine Besylate", "Norvasc", True, 5.0, 240.0, "cardio"),
    ("Losartan Potassium", "Cozaar", True, 8.0, 150.0, "cardio"),
    ("Metoprolol Succinate", "Toprol XL", True, 14.0, 95.0, "cardio"),
    ("Clopidogrel Bisulfate", "Plavix", True, 7.0, 280.0, "cardio"),
    ("Apixaban", "Eliquis", False, 0.0, 520.0, "cardio"),
    ("Rivaroxaban", "Xarelto", False, 0.0, 510.0, "cardio"),
    ("Metformin HCl", "Glucophage", True, 6.0, 120.0, "endo"),
    ("Glipizide", "Glucotrol", True, 5.0, 70.0, "endo"),
    ("Sitagliptin Phosphate", "Januvia", False, 0.0, 490.0, "endo"),
    ("Empagliflozin", "Jardiance", False, 0.0, 560.0, "endo"),
    ("Insulin Glargine,Hum.Rec.Anlog", "Lantus Solostar", False, 0.0, 430.0, "endo"),
    ("Levothyroxine Sodium", "Synthroid", True, 10.0, 45.0, "endo"),
    ("Sertraline HCl", "Zoloft", True, 6.0, 330.0, "psych"),
    ("Escitalopram Oxalate", "Lexapro", True, 7.0, 380.0, "psych"),
    ("Quetiapine Fumarate", "Seroquel", True, 12.0, 700.0, "psych"),
    ("Aripiprazole", "Abilify", True, 20.0, 1100.0, "psych"),
    ("Lurasidone HCl", "Latuda", False, 0.0, 1400.0, "psych"),
    ("Omeprazole", "Prilosec", True, 6.0, 200.0, "general"),
    ("Pantoprazole Sodium", "Protonix", True, 7.0, 330.0, "general"),
    ("Gabapentin", "Neurontin", True, 9.0, 420.0, "pain"),
    ("Pregabalin", "Lyrica", True, 14.0, 610.0, "pain"),
    ("Oxycodone HCl", "Oxycontin", True, 40.0, 520.0, "opioid_la"),
    ("Hydrocodone/Acetaminophen", "Norco", True, 15.0, 160.0, "opioid"),
    ("Tramadol HCl", "Ultram", True, 8.0, 140.0, "opioid"),
    ("Fluticasone/Salmeterol", "Advair Diskus", True, 90.0, 420.0, "general"),
    ("Tiotropium Bromide", "Spiriva", False, 0.0, 480.0, "general"),
]
CLASS_AFFINITY = {
    # specialty -> relative prescribing weight per drug class
    "Internal Medicine": {"cardio": 3, "endo": 2, "general": 2, "psych": 0.5, "pain": 0.7,
                          "opioid": 0.4, "opioid_la": 0.05},
    "Family Practice": {"cardio": 2.5, "endo": 2, "general": 2, "psych": 0.7, "pain": 0.8,
                        "opioid": 0.5, "opioid_la": 0.05},
    "Nurse Practitioner": {"cardio": 2, "endo": 1.5, "general": 2, "psych": 1, "pain": 0.8,
                           "opioid": 0.5, "opioid_la": 0.05},
    "Physician Assistant": {"cardio": 1.5, "endo": 1, "general": 2, "psych": 0.6, "pain": 1,
                            "opioid": 0.8, "opioid_la": 0.1},
    "Cardiology": {"cardio": 6, "endo": 0.5, "general": 0.5, "psych": 0.05, "pain": 0.1,
                   "opioid": 0.05, "opioid_la": 0.01},
    "Endocrinology": {"cardio": 1, "endo": 6, "general": 0.3, "psych": 0.05, "pain": 0.1,
                      "opioid": 0.02, "opioid_la": 0.01},
    "Psychiatry": {"cardio": 0.1, "endo": 0.2, "general": 0.2, "psych": 6, "pain": 0.5,
                   "opioid": 0.05, "opioid_la": 0.01},
    "Pain Management": {"cardio": 0.2, "endo": 0.1, "general": 0.3, "psych": 0.3, "pain": 4,
                        "opioid": 4, "opioid_la": 1.5},
}  # fmt: skip
NATURES = [
    ("Food and Beverage", 0.80, 25.0),
    ("Travel and Lodging", 0.04, 600.0),
    ("Consulting Fee", 0.03, 2500.0),
    ("Compensation for services other than consulting, including serving as faculty or as a "
     "speaker at a venue other than a continuing education program", 0.07, 2000.0),
    ("Education", 0.04, 150.0),
    ("Gift", 0.02, 60.0),
]  # fmt: skip
MANUFACTURERS = [(f"1000000{i:05d}", f"Synthetic Pharma {chr(65 + i)} Inc.") for i in range(12)]
EXCLUSION_TYPES_WINDOW = ["1128b4", "1128a1", "1128a3", "1128a4", "1128b7", "1128b5"]


@dataclass
class SyntheticData:
    tables: dict[str, pd.DataFrame]

    def __getitem__(self, name: str) -> pd.DataFrame:
        return self.tables[name]


def _fmt_mdy(d: date) -> str:
    return d.strftime("%m/%d/%Y")


def _num(x: float, ndigits: int = 2) -> str:
    return f"{x:.{ndigits}f}"


def _npi(rng: np.random.Generator, used: set[str]) -> str:
    while True:
        npi = str(rng.integers(1_000_000_000, 1_999_999_999))
        if npi not in used:
            used.add(npi)
            return npi


def generate(n_prescribers: int = 4000, seed: int = 7, data_year: int = 2021) -> SyntheticData:
    """Build synthetic raw tables with planted, known relationships.

    * Industry-paid prescribers get a higher brand propensity.
    * A latent risk factor raises volume, cost, opioid share and payments, and
      drives the probability of an OIG exclusion after the data year.
    """
    rng = np.random.default_rng(seed)
    used: set[str] = set()
    specialties = list(SPECIALTIES)
    spec_p = np.array([SPECIALTIES[s][0] for s in specialties])
    states = list(STATES)
    state_p = np.array(list(STATES.values()))

    presc = pd.DataFrame(
        {
            "npi": [_npi(rng, used) for _ in range(n_prescribers)],
            "specialty": rng.choice(specialties, n_prescribers, p=spec_p / spec_p.sum()),
            "state": rng.choice(states, n_prescribers, p=state_p / state_p.sum()),
        }
    )
    presc["risk"] = rng.standard_normal(n_prescribers)
    presc["case_mix"] = rng.normal(1.2, 0.25, n_prescribers).clip(0.5, 3.0)
    p_paid = presc["specialty"].map(lambda s: SPECIALTIES[s][3]) + 0.08 * presc["risk"]
    presc["paid"] = rng.random(n_prescribers) < p_paid.clip(0.02, 0.98)
    presc["volume"] = np.exp(rng.normal(6.4, 0.8, n_prescribers) + 0.35 * presc["risk"])
    presc.loc[rng.random(n_prescribers) < 0.06, "volume"] = rng.uniform(15, 90)  # low-volume
    base_brand = presc["specialty"].map(lambda s: SPECIALTIES[s][1])
    logit = np.log(base_brand / (1 - base_brand)) + 0.45 * presc["paid"] + 0.25 * presc["risk"]
    presc["brand_prop"] = 1 / (1 + np.exp(-(logit + rng.normal(0, 0.35, n_prescribers))))
    presc["entity"] = np.where(rng.random(n_prescribers) < 0.02, "O", "I")

    drug_rows = []
    for row in presc.itertuples(index=False):
        affinity = CLASS_AFFINITY[row.specialty]
        weights = np.array([affinity[d[5]] for d in DRUGS]) * rng.gamma(2.0, 0.5, len(DRUGS))
        if row.specialty != "Pain Management":
            opioid_boost = np.exp(0.6 * max(row.risk, 0))
            weights *= [opioid_boost if d[5].startswith("opioid") else 1.0 for d in DRUGS]
        weights /= weights.sum()
        fills = rng.multinomial(max(int(row.volume), 1), weights)
        for (generic, brand, multi, g_cost, b_cost, _), n in zip(DRUGS, fills, strict=True):
            if n == 0:
                continue
            if multi:
                n_brand = rng.binomial(n, row.brand_prop)
                parts = [(brand, n_brand, b_cost), (generic, n - n_brand, g_cost)]
            else:
                parts = [(brand, n, b_cost)]
            for name, n_fill, unit_cost in parts:
                claims = round(n_fill / 1.15)
                if claims < 11:  # CMS suppression rule for drug-level rows
                    continue
                cost = n_fill * unit_cost * rng.lognormal(0.1 * row.risk, 0.12)
                drug_rows.append(
                    {
                        "prscrbr_npi": row.npi,
                        "prscrbr_last_org_name": f"Last{row.npi[-4:]}",
                        "prscrbr_first_name": f"First{row.npi[-3:]}",
                        "prscrbr_city": "Springfield",
                        "prscrbr_state_abrvtn": row.state,
                        "prscrbr_type": row.specialty,
                        "prscrbr_type_src": "S",
                        "brnd_name": name,
                        "gnrc_name": generic,
                        "tot_clms": str(claims),
                        "tot_30day_fills": _num(n_fill, 1),
                        "tot_day_suply": str(int(n_fill * 30)),
                        "tot_drug_cst": _num(cost),
                        "tot_benes": str(max(int(claims / 3.5), 11)) if claims > 40 else None,
                    }
                )
    part_d_drug = pd.DataFrame(drug_rows)

    agg = part_d_drug.assign(
        fills=part_d_drug["tot_30day_fills"].astype(float),
        cost=part_d_drug["tot_drug_cst"].astype(float),
        claims=part_d_drug["tot_clms"].astype(int),
        is_brand=[
            b.upper() != g.upper() and not b.upper().startswith(g.upper() + " ")
            for b, g in zip(part_d_drug["brnd_name"], part_d_drug["gnrc_name"], strict=True)
        ],
        is_opioid=part_d_drug["gnrc_name"].isin([d[0] for d in DRUGS if d[5].startswith("opioid")]),
        is_opioid_la=part_d_drug["gnrc_name"].isin([d[0] for d in DRUGS if d[5] == "opioid_la"]),
    )
    agg["brand_claims"] = agg["claims"] * agg["is_brand"]
    agg["brand_cost"] = agg["cost"] * agg["is_brand"]
    agg["opioid_claims"] = agg["claims"] * agg["is_opioid"]
    agg["opioid_la_claims"] = agg["claims"] * agg["is_opioid_la"]
    per_npi = agg.groupby("prscrbr_npi").agg(
        claims=("claims", "sum"),
        fills=("fills", "sum"),
        cost=("cost", "sum"),
        brand_claims=("brand_claims", "sum"),
        brand_cost=("brand_cost", "sum"),
        opioid_claims=("opioid_claims", "sum"),
        opioid_la_claims=("opioid_la_claims", "sum"),
    )
    presc = presc.join(per_npi, on="npi", how="inner")
    n = len(presc)
    benes = (presc["claims"] / rng.uniform(2.5, 5.0, n)).clip(lower=11).round().astype(int)
    dual_share = rng.beta(2, 6, n) + 0.05 * (presc["case_mix"] - 1.2)
    dual = (benes * dual_share.clip(0.01, 0.95)).round().astype(int)
    female = (benes * rng.beta(12, 10, n)).round().astype(int)
    part_d_prescriber = pd.DataFrame(
        {
            "prscrbr_npi": presc["npi"],
            "prscrbr_ent_cd": presc["entity"],
            "prscrbr_last_org_name": "Last" + presc["npi"].str[-4:],
            "prscrbr_first_name": "First" + presc["npi"].str[-3:],
            "prscrbr_crdntls": presc["specialty"]
            .map({"Nurse Practitioner": "NP", "Physician Assistant": "PA-C"})
            .fillna("MD"),
            "prscrbr_city": "Springfield",
            "prscrbr_state_abrvtn": presc["state"],
            "prscrbr_zip5": [f"{z:05d}" for z in rng.integers(10000, 99999, n)],
            "prscrbr_ruca": [_num(x, 1) for x in rng.choice([1, 1, 1, 2, 4, 7, 10], n)],
            "prscrbr_type": presc["specialty"],
            "tot_clms": presc["claims"].astype(str),
            "tot_30day_fills": presc["fills"].map(lambda x: _num(x, 1)),
            "tot_drug_cst": presc["cost"].map(_num),
            "tot_day_suply": (presc["fills"] * 30).astype(int).astype(str),
            "tot_benes": benes.astype(str),
            "brnd_tot_clms": presc["brand_claims"].astype(int).astype(str),
            "brnd_tot_drug_cst": presc["brand_cost"].map(_num),
            "gnrc_tot_clms": (presc["claims"] - presc["brand_claims"]).astype(int).astype(str),
            "gnrc_tot_drug_cst": (presc["cost"] - presc["brand_cost"]).map(_num),
            "othr_tot_clms": "0",
            "lis_tot_clms": (presc["claims"] * dual_share.clip(0, 1) * 1.3)
            .clip(upper=presc["claims"])
            .astype(int)
            .astype(str),
            "opioid_tot_clms": presc["opioid_claims"].astype(int).astype(str),
            "opioid_la_tot_clms": presc["opioid_la_claims"].astype(int).astype(str),
            "opioid_prscrbr_rate": (100 * presc["opioid_claims"] / presc["claims"]).map(_num),
            "antbtc_tot_clms": None,
            "antpsyct_ge65_tot_clms": None,
            "bene_avg_age": [_num(x, 0) for x in rng.normal(73, 4, n).clip(60, 90)],
            "bene_dual_cnt": dual.astype(str),
            "bene_ndual_cnt": (benes - dual).astype(str),
            "bene_feml_cnt": female.astype(str),
            "bene_male_cnt": (benes - female).astype(str),
            "bene_avg_risk_scre": presc["case_mix"].map(lambda x: _num(x, 4)),
        }
    )

    # ---- Open Payments ------------------------------------------------------
    pay_rows = []
    brand_names = [d[1] for d in DRUGS]
    record_id = 900_000_000
    for row in presc[presc["paid"]].itertuples(index=False):
        n_records = 1 + rng.poisson(3 + 2 * max(row.risk, 0))
        for _ in range(n_records):
            nature_idx = rng.choice(len(NATURES), p=[n[1] for n in NATURES])
            nature, _, scale = NATURES[nature_idx]
            mfr_id, mfr_name = MANUFACTURERS[rng.integers(len(MANUFACTURERS))]
            record_id += 1
            is_device = rng.random() < 0.08
            pay_date = date(data_year, 1, 1) + timedelta(days=int(rng.integers(0, 365)))
            pay_rows.append(
                {
                    "record_id": str(record_id),
                    "covered_recipient_type": "Covered Recipient Physician",
                    "covered_recipient_npi": row.npi if rng.random() > 0.01 else None,
                    "covered_recipient_profile_id": str(rng.integers(100000, 999999)),
                    "covered_recipient_first_name": "FIRST",
                    "covered_recipient_last_name": "LAST",
                    "recipient_state": row.state,
                    "covered_recipient_primary_type_1": "Medical Doctor",
                    "covered_recipient_specialty_1": row.specialty,
                    "applicable_manufacturer_or_applicable_gpo_making_payment_id": mfr_id,
                    "applicable_manufacturer_or_applicable_gpo_making_payment_name": mfr_name,
                    "total_amount_of_payment_usdollars": _num(rng.lognormal(np.log(scale), 0.6)),
                    "date_of_payment": _fmt_mdy(pay_date),
                    "number_of_payments_included_in_total_amount": "1",
                    "form_of_payment_or_transfer_of_value": "In-kind items and services",
                    "nature_of_payment_or_transfer_of_value": nature,
                    "related_product_indicator": "Yes",
                    "indicate_drug_or_biological_or_device_or_medical_supply_1": (
                        "Device" if is_device else "Drug"
                    ),
                    "name_of_drug_or_biological_or_device_or_medical_supply_1": (
                        "SYNTHETIC DEVICE" if is_device else rng.choice(brand_names).upper()
                    ),
                    **{
                        f"indicate_drug_or_biological_or_device_or_medical_supply_{i}": None
                        for i in range(2, 6)
                    },
                    **{
                        f"name_of_drug_or_biological_or_device_or_medical_supply_{i}": None
                        for i in range(2, 6)
                    },
                    "program_year": str(data_year),
                    "dispute_status_for_publication": "No",
                }
            )
    for _ in range(50):  # teaching hospital rows without an NPI
        record_id += 1
        pay_rows.append(
            {
                **pay_rows[0],
                "record_id": str(record_id),
                "covered_recipient_type": "Covered Recipient Teaching Hospital",
                "covered_recipient_npi": None,
            }
        )
    open_payments = pd.DataFrame(pay_rows)

    # ---- OIG exclusions -----------------------------------------------------
    leie_rows = []
    prob_later = 1 / (1 + np.exp(-(-5.6 + 1.5 * presc["risk"])))
    later = rng.random(n) < prob_later
    prior = (~later) & (rng.random(n) < 0.004)
    window_days = (date(2026, 8, 31) - date(data_year + 1, 1, 1)).days
    for row, is_later, is_prior in zip(presc.itertuples(index=False), later, prior, strict=True):
        if not (is_later or is_prior):
            continue
        if is_later:
            excl = date(data_year + 1, 1, 1) + timedelta(days=int(rng.integers(0, window_days)))
            etype = rng.choice(EXCLUSION_TYPES_WINDOW)
        else:
            excl = date(data_year - 2, 1, 1) + timedelta(days=int(rng.integers(0, 3 * 365)))
            etype = "1128b4"
        leie_rows.append(
            {
                "lastname": f"LAST{row.npi[-4:]}",
                "firstname": f"FIRST{row.npi[-3:]}",
                "midname": None,
                "busname": None,
                "general": "IND- LIC HC SERV PRO",
                "specialty": row.specialty.upper(),
                "npi": row.npi,
                "city": "SPRINGFIELD",
                "state": row.state,
                "zip": "00000",
                "excltype": etype,
                "excldate": excl.strftime("%Y%m%d"),
                "reindate": "00000000",
                "waiverdate": "00000000",
                "wvrstate": None,
            }
        )
    for i in range(300):  # exclusions unrelated to any prescriber, incl. entities
        excl = date(2005, 1, 1) + timedelta(days=int(rng.integers(0, 7500)))
        is_entity = i % 5 == 0
        leie_rows.append(
            {
                "lastname": None if is_entity else f"OTHER{i}",
                "firstname": None if is_entity else "PERSON",
                "midname": None,
                "busname": f"SYNTHETIC PHARMACY {i}" if is_entity else None,
                "general": "PHARMACY" if is_entity else "IND- NURSING PROFESSION",
                "specialty": None,
                "npi": "0000000000" if i % 2 else _npi(rng, used),
                "city": "ELSEWHERE",
                "state": rng.choice(states),
                "zip": "00000",
                "excltype": rng.choice(["1128a1", "1128b4", "1128b7", "1128a2"]),
                "excldate": excl.strftime("%Y%m%d"),
                "reindate": "00000000",
                "waiverdate": "00000000",
                "wvrstate": None,
            }
        )
    leie = pd.DataFrame(leie_rows)

    # ---- NPPES ---------------------------------------------------------------
    taxonomy = {
        "Internal Medicine": "207R00000X", "Family Practice": "207Q00000X",
        "Nurse Practitioner": "363L00000X", "Physician Assistant": "363A00000X",
        "Cardiology": "207RC0000X", "Endocrinology": "207RE0101X",
        "Psychiatry": "2084P0800X", "Pain Management": "208VP0014X",
    }  # fmt: skip
    nppes = pd.DataFrame(
        {
            "npi": presc["npi"],
            "entity_type_code": np.where(presc["entity"] == "O", "2", "1"),
            "provider_last_name_legal_name": "Last" + presc["npi"].str[-4:],
            "provider_first_name": "First" + presc["npi"].str[-3:],
            "provider_credential_text": "MD",
            "provider_business_practice_location_address_city_name": "SPRINGFIELD",
            "provider_business_practice_location_address_state_name": presc["state"],
            "provider_business_practice_location_address_postal_code": "123456789",
            "provider_enumeration_date": [
                _fmt_mdy(date(2005, 5, 23) + timedelta(days=int(d)))
                for d in rng.integers(0, 5000, n)
            ],
            "last_update_date": _fmt_mdy(date(2024, 1, 1)),
            "npi_deactivation_reason_code": None,
            "npi_deactivation_date": None,
            "npi_reactivation_date": None,
            "is_sole_proprietor": rng.choice(["Y", "N", "X"], n),
            "healthcare_provider_taxonomy_code_1": "174400000X",
            "healthcare_provider_primary_taxonomy_switch_1": "N",
            "healthcare_provider_taxonomy_code_2": presc["specialty"].map(taxonomy),
            "healthcare_provider_primary_taxonomy_switch_2": "Y",
            **{
                f"healthcare_provider_{kind}_{i}": None
                for i in range(3, 16)
                for kind in ("taxonomy_code", "primary_taxonomy_switch")
            },
        }
    )

    return SyntheticData(
        tables={
            "part_d_prescriber_drug": part_d_drug,
            "part_d_prescriber": part_d_prescriber,
            "open_payments_general": open_payments,
            "leie_exclusions": leie,
            "nppes_providers": nppes,
        }
    )


def write_synthetic_parquet(
    cfg: PipelineConfig, out_dir: Path, n_prescribers: int = 4000, seed: int = 7
) -> dict[str, Path]:
    """Generate synthetic raw tables and write them in the loader's Parquet layout."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    from partd_risk.ingest.stage import arrow_schema

    data = generate(n_prescribers=n_prescribers, seed=seed, data_year=cfg.data_year)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, frame in data.tables.items():
        source = cfg.source(name)
        missing = set(source.columns) - set(frame.columns)
        extra = set(frame.columns) - set(source.columns)
        if missing or extra:
            raise AssertionError(
                f"{name}: synthetic layout drift (missing={missing}, extra={extra})"
            )
        frame = frame[list(source.columns)].astype(object).where(frame.notna(), None)
        path = out_dir / f"{source.raw_table}.parquet"
        table = pa.Table.from_pandas(frame, schema=arrow_schema(source), preserve_index=False)
        pq.write_table(table, path)
        files[name] = path
        log.info("Synthetic %s: %s rows", name, f"{len(frame):,}")
    return files
