"""Executable canonical-weather contract and verified CSV handoff to existing ML."""

import json
from pathlib import Path

import duckdb
import pandas as pd

from src.data.preprocess import NAMES
from src.data.validate_data import validate_soil, validate_weather
from src.dataops.dlt_pipeline import source_frame
from src.utils.provenance import file_hash, write_json

COLUMNS = [
    *NAMES.values(),
    "date",
    "site_id",
    "latitude",
    "longitude",
    "field_capacity",
    "wilting_point",
]


def validate_contract(frame: pd.DataFrame, cfg: dict) -> None:
    if list(frame.columns) != COLUMNS:
        raise ValueError(f"Expected canonical columns, in order: {COLUMNS}")
    validate_weather(frame)
    sites = {site["id"]: site for site in cfg["data"]["sites"]}
    if set(frame.site_id) != set(sites):
        raise ValueError("Expected every configured site and no unknown sites")
    expected = list(pd.date_range(cfg["data"]["start"], cfg["data"]["end"]))
    for site_id, group in frame.groupby("site_id"):
        if list(group.date) != expected:
            raise ValueError(f"Incomplete configured date coverage for {site_id}")
        site = sites[site_id]
        for key in ("latitude", "longitude", "field_capacity", "wilting_point"):
            if not pd.api.types.is_numeric_dtype(group[key]) or not group[key].eq(site[key]).all():
                raise ValueError(f"Static scenario mismatch: {site_id}/{key}")
        validate_soil(site["field_capacity"], site["wilting_point"], cfg["proxy"]["root_depth_m"])


def quality(cfg: dict, db: Path, output: Path) -> dict:
    with duckdb.connect(str(db), read_only=True) as con:
        frame = con.sql("select * from weather_analytics.ml_weather order by site_id, date").df()
        staging = con.sql("select * from weather_staging.stg_weather order by site_id, date").df()
    frame["date"] = pd.to_datetime(frame.date)
    validate_contract(frame, cfg)
    # Compare all canonical values against the original normalization path and
    # every staging row's provenance against independently verified snapshots.
    expected = source_frame(cfg)
    pd.testing.assert_frame_equal(
        frame.reset_index(drop=True), expected[COLUMNS], check_dtype=False, check_exact=True
    )
    provenance = ["site_id", "source", "snapshot_id", "snapshot_sha256"]
    pd.testing.assert_frame_equal(
        staging[provenance].reset_index(drop=True), expected[provenance], check_dtype=False
    )
    if staging.ingested_at.isna().any():
        raise ValueError("Missing ingestion timestamps")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".csv.tmp")
    frame.to_csv(temporary, index=False, date_format="%Y-%m-%d")
    temporary.replace(output)
    report = {
        "status": "passed",
        "rows": len(frame),
        "sites": sorted(frame.site_id.unique()),
        "canonical_equivalence": "exact",
        "weather_sha256": file_hash(output),
        "snapshots": json.loads((db.parent / "ingestion.json").read_text())["snapshots"],
    }
    write_json(output.parent / "quality.json", report)
    return report
