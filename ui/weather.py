"""Build API requests with the existing NASA collector and training normalization.

UI downloads live in a separate cache; batch snapshots and manifests stay immutable.
"""

import copy
import json
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from src.api.schemas import WeatherDay
from src.data.collect_data import collect, request_params, snapshot_paths, verify_snapshot
from src.data.preprocess import normalize_payload
from src.utils.config import get_path
from ui.utils import CROPS, SITES, UIError, validate_request


@dataclass
class WeatherResult:
    request: dict
    mode: str
    snapshot: str
    notice: str = ""


def supported_sites(cfg: dict) -> dict:
    return {site["id"]: site for site in cfg["data"]["sites"] if site["id"] in SITES}


def history_window(forecast_date: date, cfg: dict) -> tuple[date, date]:
    if type(forecast_date) is not date:
        raise UIError("Choose a valid prediction date.")
    if forecast_date > date.today():
        raise UIError(
            "Prediction date cannot be in the future: complete observations are required."
        )
    days = cfg["features"]["history_days"]
    return forecast_date - timedelta(days=days), forecast_date - timedelta(days=1)


def snapshot_request(
    raw: Path, manifest: Path, cfg: dict, site: dict, start: date, end: date, crop: str
) -> dict:
    meta = json.loads(manifest.read_text())
    expected = request_params(cfg, site)
    recorded = meta["request"]
    endpoint = urlsplit(cfg["data"]["endpoint"])
    source = urlsplit(meta["url"])
    if meta["source"] != "NASA POWER" or (source.scheme, source.netloc, source.path) != (
        endpoint.scheme,
        endpoint.netloc,
        endpoint.path,
    ):
        raise ValueError("Snapshot source does not match configured NASA POWER endpoint")
    for key, value in expected.items():
        if key not in ("start", "end") and recorded.get(key) != value:
            raise ValueError(f"Snapshot request mismatch: {key}")
    if (
        not recorded["start"]
        <= start.strftime("%Y%m%d")
        <= end.strftime("%Y%m%d")
        <= recorded["end"]
    ):
        raise ValueError("Snapshot does not cover the requested period")
    frame = normalize_payload(verify_snapshot(raw, manifest), site)
    frame = frame.loc[
        frame.date.between(str(start), str(end)), list(WeatherDay.model_fields)
    ].copy()
    frame["date"] = frame.date.dt.strftime("%Y-%m-%d")
    payload = validate_request(
        {"crop": crop, "site_id": site["id"], "history": frame.to_dict("records")}
    )
    if payload["history"][0]["date"] != str(start) or payload["history"][-1]["date"] != str(end):
        raise ValueError("Snapshot has incomplete history coverage")
    return payload


def cached_history(
    cfg: dict, site: dict, start: date, end: date, crop: str
) -> WeatherResult | None:
    raw_dir = get_path(cfg, "raw")
    for directory in (raw_dir, raw_dir / "ui_weather"):
        for manifest in sorted(directory.glob(f"{site['id']}_*.manifest.json")):
            raw = manifest.with_name(manifest.name.replace(".manifest.json", ".json"))
            try:
                payload = snapshot_request(raw, manifest, cfg, site, start, end, crop)
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                # Unsuitable/incomplete/tampered snapshots are never served.
                continue
            return WeatherResult(payload, "Offline cached snapshot", raw.name)
    return None


def get_weather_history(
    site_id: str, forecast_date: date, crop: str, cfg: dict, prefer_live: bool = False
) -> WeatherResult:
    sites = supported_sites(cfg)
    if site_id not in sites:
        raise UIError("This site is outside the configured project locations.")
    if crop not in CROPS or crop != cfg["proxy"]["crop"]:
        raise UIError("This crop is outside the configured project scenario.")
    start, end = history_window(forecast_date, cfg)
    site = sites[site_id]
    cached = cached_history(cfg, site, start, end, crop)
    if cached is not None and not prefer_live:
        return cached
    request_cfg = copy.deepcopy(cfg)
    request_cfg["data"].update(start=str(start), end=str(end), sites=[site])
    request_cfg["paths"]["raw"] = str(get_path(cfg, "raw") / "ui_weather")
    raw, manifest = snapshot_paths(request_cfg, site)
    existed = raw.exists() and manifest.exists()
    try:
        # Reuse the existing downloader, request parameters, LST convention and lineage.
        # It protects exact cached requests even when live-first is selected.
        collect(request_cfg)
        payload = snapshot_request(raw, manifest, cfg, site, start, end, crop)
        return WeatherResult(payload, "Offline cached snapshot" if existed else "Live", raw.name)
    except (OSError, RuntimeError, ValueError, KeyError, TypeError, AttributeError) as exc:
        if cached is not None:
            cached.notice = "NASA retrieval failed; using a verified local NASA snapshot."
            return cached
        raise UIError(
            "NASA POWER data are unavailable or incomplete, and no verified local snapshot "
            "covers this period. Recent observations may not be published yet. "
            "Choose an earlier date or switch to Manual / File and Load Example."
        ) from exc
