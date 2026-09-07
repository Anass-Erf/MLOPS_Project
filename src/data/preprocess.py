"""Verify snapshots, normalize weather names/units, and retain unmodified raw files."""

import pandas as pd

from src.data.collect_data import snapshot_paths, verify_snapshot
from src.data.validate_data import validate_weather
from src.utils.config import get_path, load_config
from src.utils.logger import get_logger
from src.utils.provenance import receipt, write_json

NAMES = {
    "T2M": "temperature",
    "T2M_MAX": "temperature_max",
    "T2M_MIN": "temperature_min",
    "PRECTOTCORR": "precipitation",
    "RH2M": "humidity",
    "WS2M": "wind_speed",
    "ALLSKY_SFC_SW_DWN": "solar_radiation",
}
UNITS = {
    "T2M": "C",
    "T2M_MAX": "C",
    "T2M_MIN": "C",
    "PRECTOTCORR": "mm/day",
    "RH2M": "%",
    "WS2M": "m/s",
}
LOG = get_logger(__name__)


def normalize_payload(payload: dict, site: dict) -> pd.DataFrame:
    parameters = payload["properties"]["parameter"]
    missing = set(NAMES) - parameters.keys()
    if missing:
        raise ValueError(f"NASA missing parameters: {sorted(missing)}")
    for name, expected in UNITS.items():
        actual = payload["parameters"][name]["units"]
        if actual != expected:
            raise ValueError(f"Unexpected units for {name}: {actual}; expected {expected}")
    df = pd.DataFrame({k: parameters[k] for k in NAMES}).rename(columns=NAMES)
    df = df.replace(payload["header"].get("fill_value", -999), float("nan"))
    df["date"] = pd.to_datetime(df.index, format="%Y%m%d", errors="raise")
    radiation_unit = payload["parameters"]["ALLSKY_SFC_SW_DWN"]["units"]
    if radiation_unit == "kW-hr/m^2/day":
        df["solar_radiation"] *= 3.6
    elif radiation_unit != "MJ/m^2/day":
        raise ValueError(f"Unknown radiation unit: {radiation_unit}")
    df["site_id"] = site["id"]
    for key in ("latitude", "longitude", "field_capacity", "wilting_point"):
        df[key] = site[key]
    return df.sort_values("date").reset_index(drop=True)


def preprocess(cfg: dict) -> pd.DataFrame:
    frames, inputs = [], []
    for site in cfg["data"]["sites"]:
        raw, manifest = snapshot_paths(cfg, site)
        frames.append(normalize_payload(verify_snapshot(raw, manifest), site))
        inputs.extend([raw, manifest])
    df = pd.concat(frames, ignore_index=True).sort_values(["site_id", "date"])
    validate_weather(df)
    expected = pd.date_range(cfg["data"]["start"], cfg["data"]["end"])
    for site, group in df.groupby("site_id"):
        if list(group.date) != list(expected):
            raise ValueError(f"NASA date coverage incomplete for {site}")
    path = get_path(cfg, "interim")
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, date_format="%Y-%m-%d")
    quality = get_path(cfg, "artifacts") / "data_quality.json"
    write_json(
        quality,
        {
            "rows": len(df),
            "sites": df.site_id.nunique(),
            "missing": df.isna().sum().to_dict(),
            "duplicates": 0,
            "start": str(df.date.min().date()),
            "end": str(df.date.max().date()),
            "status": "passed",
            "radiation_unit": "MJ/m2/day",
        },
    )
    receipt(cfg, "preprocess", inputs, [path, quality])
    LOG.info("Validated %d daily weather observations", len(df))
    return df


if __name__ == "__main__":
    preprocess(load_config())
