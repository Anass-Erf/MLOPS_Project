"""Load genuine, verified NASA snapshots through dlt into DuckDB.

Raw table values already use project units, via the existing normalization code.
The raw JSON and manifest remain the immutable source of truth.
"""

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import pandas as pd

from src.data.collect_data import collect, request_params, snapshot_paths, verify_snapshot
from src.data.preprocess import NAMES, normalize_payload
from src.data.validate_data import validate_weather
from src.dataops.settings import database, workspace
from src.utils.config import load_config
from src.utils.provenance import write_json


def source_frame(cfg: dict) -> pd.DataFrame:
    frames = []
    for site in cfg["data"]["sites"]:
        raw, manifest = snapshot_paths(cfg, site)
        meta = json.loads(manifest.read_text())
        endpoint, recorded = urlsplit(cfg["data"]["endpoint"]), urlsplit(meta["url"])
        if (
            meta["source"] != "NASA POWER"
            or meta["request"] != request_params(cfg, site)
            or (endpoint.scheme, endpoint.netloc, endpoint.path)
            != (recorded.scheme, recorded.netloc, recorded.path)
        ):
            raise ValueError(f"Snapshot provenance mismatch: {manifest}")
        frame = normalize_payload(verify_snapshot(raw, manifest), site)
        frame["source"] = meta["source"]
        frame["snapshot_id"] = raw.name
        frame["snapshot_sha256"] = meta["sha256"]
        frames.append(frame)
    result = pd.concat(frames, ignore_index=True).sort_values(["site_id", "date"])
    validate_weather(result)
    expected = list(pd.date_range(cfg["data"]["start"], cfg["data"]["end"]))
    for site, group in result.groupby("site_id"):
        if list(group.date) != expected:
            raise ValueError(f"Incomplete configured date coverage for {site}")
    return result.reset_index(drop=True)


def ingest(cfg: dict, db: Path, state: Path, offline: bool = True) -> dict:
    os.environ.setdefault("RUNTIME__DLTHUB_TELEMETRY", "false")
    import dlt
    from dlt.destinations import duckdb

    collect(cfg, offline=offline)
    frame = source_frame(cfg)
    frame = frame.rename(columns={v: k.lower() for k, v in NAMES.items()} | {"date": "observed_on"})
    frame["observed_on"] = frame.observed_on.dt.strftime("%Y-%m-%d")
    frame["ingested_at"] = datetime.now(timezone.utc).isoformat()
    db.parent.mkdir(parents=True, exist_ok=True)
    pipeline = dlt.pipeline(
        pipeline_name="nasa_weather",
        destination=duckdb(credentials=str(db)),
        dataset_name="raw",
        pipelines_dir=str(state),
    )
    # Full verified snapshots are small. Replace avoids duplicates on repeated demos;
    # validate everything before replacing any destination data.
    info = pipeline.run(
        frame.to_dict("records"),
        table_name="raw_weather",
        write_disposition="replace",
        primary_key=["site_id", "observed_on"],
    )
    info.raise_on_failed_jobs()
    report = {
        "rows": len(frame),
        "database": str(db),
        "table": "raw.raw_weather",
        "load_ids": info.loads_ids,
        "snapshots": frame[["site_id", "snapshot_id", "snapshot_sha256"]]
        .drop_duplicates()
        .to_dict("records"),
    }
    write_json(db.parent / "ingestion.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live", action="store_true", help="Allow existing NASA collector downloads"
    )
    args = parser.parse_args()
    print(
        json.dumps(ingest(load_config(), database(), workspace() / "dlt", not args.live), indent=2)
    )
