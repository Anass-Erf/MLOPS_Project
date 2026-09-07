"""One causal weather feature implementation for both offline training and API."""

import numpy as np
import pandas as pd

from src.data.validate_data import validate_target, validate_weather
from src.features.water_balance import crop_calendar, reference_et, water_balance
from src.utils.config import get_path, load_config
from src.utils.logger import get_logger
from src.utils.provenance import file_hash, object_hash, receipt, write_json

FEATURES = [
    "temperature",
    "temperature_max",
    "temperature_min",
    "precipitation",
    "humidity",
    "wind_speed",
    "solar_radiation",
    "temperature_range",
    "vpd_kpa",
    "et0",
    "rainfall_7d",
    "rainfall_30d",
    "temperature_7d",
    "water_balance_30d",
    "precipitation_lag1",
    "doy_sin",
    "doy_cos",
    "crop_age",
    "kc",
    "latitude",
    "longitude",
    "field_capacity",
    "wilting_point",
    "root_depth_m",
    "taw_mm",
]
LOG = get_logger(__name__)


def weather_features(weather: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Rows describe end-of-day information; rolling windows include that day.

    The first 29 rows of each site have incomplete histories and are not usable.
    No imputer, scaler or learned statistic is fit during feature construction.
    """
    validate_weather(weather)
    groups = []
    for _, group in weather.groupby("site_id", sort=True):
        g = group.copy().reset_index(drop=True)
        g["temperature_range"] = g.temperature_max - g.temperature_min
        saturation = 0.6108 * np.exp(17.27 * g.temperature / (g.temperature + 237.3))
        g["vpd_kpa"] = saturation * (1 - g.humidity / 100)
        g["et0"] = reference_et(g)
        g["rainfall_7d"] = g.precipitation.rolling(7, min_periods=7).sum()
        g["rainfall_30d"] = g.precipitation.rolling(30, min_periods=30).sum()
        g["temperature_7d"] = g.temperature.rolling(7, min_periods=7).mean()
        g["water_balance_30d"] = (g.precipitation - g.et0).rolling(30).sum()
        g["precipitation_lag1"] = g.precipitation.shift(1)
        day = g.date.dt.dayofyear
        g["doy_sin"] = np.sin(2 * np.pi * day / 365.25)
        g["doy_cos"] = np.cos(2 * np.pi * day / 365.25)
        calendar = crop_calendar(g.date, cfg["proxy"])
        g["crop_age"], g["kc"] = calendar.crop_age, calendar.kc
        g["root_depth_m"] = cfg["proxy"]["root_depth_m"]
        g["taw_mm"] = 1000 * (g.field_capacity - g.wilting_point) * g.root_depth_m
        groups.append(g)
    return pd.concat(groups, ignore_index=True)


def assign_split(target_dates: pd.Series, cfg: dict) -> np.ndarray:
    return np.select(
        [
            target_dates <= pd.Timestamp(cfg["split"]["train_end"]),
            target_dates <= pd.Timestamp(cfg["split"]["validation_end"]),
        ],
        ["train", "validation"],
        default="test",
    )


def build_features(cfg: dict) -> pd.DataFrame:
    source = get_path(cfg, "interim")
    weather = pd.read_csv(source, parse_dates=["date"])
    validate_weather(weather)
    features = weather_features(weather, cfg)
    proxy = water_balance(weather, cfg["proxy"])
    # Join explicit site/date keys rather than relying on dataframe index alignment.
    proxy["target"] = proxy.groupby("site_id").stress_today.shift(-1)
    proxy["target_active"] = proxy.groupby("site_id").active.shift(-1)
    proxy["target_date"] = proxy.groupby("site_id").date.shift(-1)
    joined = features.merge(
        proxy[
            ["site_id", "date", "stress_today", "target", "target_date", "target_active", "active"]
        ],
        on=["site_id", "date"],
        validate="one_to_one",
    )
    first_valid = pd.Timestamp(cfg["data"]["start"]) + pd.Timedelta(
        days=cfg["proxy"]["spinup_days"]
    )
    joined = joined.loc[
        (joined.date >= first_valid) & joined.active & joined.target_active.eq(True)
    ].dropna(subset=FEATURES + ["target"])
    joined["split"] = assign_split(joined.target_date, cfg)
    validate_target(joined.target)
    if set(joined.split) != {"train", "validation", "test"}:
        raise ValueError("Every chronological split must contain samples")
    output = get_path(cfg, "processed")
    output.parent.mkdir(parents=True, exist_ok=True)
    columns = ["site_id", "date", "target_date", "split", *FEATURES, "stress_today", "target"]
    joined = joined[columns].sort_values(["date", "site_id"]).reset_index(drop=True)
    joined.to_csv(output, index=False, date_format="%Y-%m-%d")
    audit = get_path(cfg, "artifacts") / "proxy_audit.csv"
    proxy.drop(columns=["target", "target_active", "target_date"]).to_csv(audit, index=False)
    manifest = get_path(cfg, "artifacts") / "dataset_manifest.json"
    write_json(
        manifest,
        {
            "dataset_sha256": file_hash(output),
            "weather_sha256": file_hash(source),
            "config_sha256": object_hash(cfg),
            "target": "next_day_1_minus_Ks_proxy",
            "features": FEATURES,
            "rows": len(joined),
            "splits": {
                s: {
                    "rows": len(g),
                    "first_target": str(g.target_date.min().date()),
                    "last_target": str(g.target_date.max().date()),
                }
                for s, g in joined.groupby("split")
            },
        },
    )
    receipt(cfg, "features", [source], [output, audit, manifest])
    LOG.info("Built %d rows, split counts: %s", len(joined), joined.split.value_counts().to_dict())
    return joined


if __name__ == "__main__":
    build_features(load_config())
