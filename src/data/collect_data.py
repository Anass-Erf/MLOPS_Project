"""Download immutable, request-addressed NASA POWER JSON snapshots.

Reusing a snapshot is the default. A new request gets a new path. Raw files are
never rewritten. --offline verifies and reuses already downloaded snapshots.
"""

import argparse
import json
from datetime import datetime, timezone

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.utils.config import get_path, load_config
from src.utils.logger import get_logger
from src.utils.provenance import file_hash, object_hash, write_json

LOG = get_logger(__name__)


def request_params(cfg: dict, site: dict) -> dict:
    return {
        "parameters": ",".join(cfg["data"]["parameters"]),
        "community": cfg["data"]["community"],
        "latitude": site["latitude"],
        "longitude": site["longitude"],
        "start": cfg["data"]["start"].replace("-", ""),
        "end": cfg["data"]["end"].replace("-", ""),
        "format": "JSON",
        "time-standard": "LST",
    }


def snapshot_paths(cfg: dict, site: dict):
    key = object_hash({"url": cfg["data"]["endpoint"], "params": request_params(cfg, site)})[:16]
    raw = get_path(cfg, "raw") / f"{site['id']}_{key}.json"
    return raw, raw.with_suffix(".manifest.json")


def verify_snapshot(raw, manifest) -> dict:
    meta = json.loads(manifest.read_text())
    if file_hash(raw) != meta["sha256"]:
        raise ValueError(f"Raw snapshot checksum mismatch: {raw}")
    return json.loads(raw.read_text())


def collect(cfg: dict, offline: bool = False) -> None:
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    for site in cfg["data"]["sites"]:
        raw, manifest = snapshot_paths(cfg, site)
        if raw.exists() and manifest.exists():
            verify_snapshot(raw, manifest)
            LOG.info("Verified cached snapshot %s", raw.name)
            continue
        if raw.exists() or manifest.exists():
            raise RuntimeError(f"Incomplete snapshot pair: {raw}; restore from an archive")
        if offline:
            raise FileNotFoundError(
                f"No cached snapshot for {site['id']}. Run make data online first"
            )
        params = request_params(cfg, site)
        LOG.info("Downloading %s (%s to %s)", site["id"], params["start"], params["end"])
        try:
            response = session.get(cfg["data"]["endpoint"], params=params, timeout=(15, 120))
            response.raise_for_status()
            body = response.json()
            if not body.get("properties", {}).get("parameter"):
                raise ValueError("NASA response does not contain daily parameters")
        except (requests.RequestException, ValueError) as exc:
            raise RuntimeError(
                "NASA unavailable. Reuse verified raw snapshots with --offline; "
                "no synthetic substitute is generated."
            ) from exc
        raw.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation protects immutable weather observations.
        with raw.open("xb") as handle:
            handle.write(response.content)
        write_json(
            manifest,
            {
                "source": "NASA POWER",
                "url": response.url,
                "request": params,
                "sha256": file_hash(raw),
                "downloaded_utc": datetime.now(timezone.utc).isoformat(),
                "header": body.get("header"),
                "units": body.get("parameters"),
            },
        )
        LOG.info("Saved %s (%d bytes)", raw.name, raw.stat().st_size)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    collect(load_config(), parser.parse_args().offline)
