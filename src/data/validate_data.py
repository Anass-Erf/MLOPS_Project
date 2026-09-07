"""Fail-closed checks shared by batch processing and the serving feature builder."""

import numpy as np
import pandas as pd

WEATHER_BOUNDS = {
    "temperature": (-60, 60),
    "temperature_max": (-60, 65),
    "temperature_min": (-70, 60),
    "precipitation": (0, 1000),
    "humidity": (0, 100),
    "wind_speed": (0, 75),
    "solar_radiation": (0, 50),
}


def validate_weather(df: pd.DataFrame) -> None:
    required = {"date", "site_id", *WEATHER_BOUNDS}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if df.empty or df[list(required)].isna().any().any():
        raise ValueError("Empty data or missing required values; no weather imputation is allowed")
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        raise ValueError("date must have datetime dtype")
    if df.duplicated(["site_id", "date"]).any():
        raise ValueError("Duplicate site/date observations")
    for col, (low, high) in WEATHER_BOUNDS.items():
        if not pd.api.types.is_numeric_dtype(df[col]):
            raise ValueError(f"{col} must be numeric")
        if not np.isfinite(df[col]).all() or not df[col].between(low, high).all():
            raise ValueError(f"{col} outside valid range [{low}, {high}]")
    if ((df.temperature_min > df.temperature) | (df.temperature > df.temperature_max)).any():
        raise ValueError("Temperature ordering must be minimum <= mean <= maximum")
    for _, group in df.groupby("site_id"):
        if not group.date.diff().dropna().eq(pd.Timedelta(days=1)).all():
            raise ValueError("Dates must be ordered and consecutive within each site")
    if "soil_moisture" in df and (
        df.soil_moisture.isna().any() or not df.soil_moisture.between(0, 1).all()
    ):
        raise ValueError("soil_moisture must be finite and in [0, 1] m3/m3")


def validate_soil(field_capacity: float, wilting_point: float, root_depth_m: float) -> None:
    if not 0 < wilting_point < field_capacity < 1 or not 0.1 <= root_depth_m <= 3:
        raise ValueError("Require 0 < wilting_point < field_capacity < 1 and root depth in [0.1,3]")


def validate_target(series: pd.Series) -> None:
    if series.empty or series.isna().any() or not series.between(0, 1).all():
        raise ValueError("Stress target must be finite, nonempty and in [0,1]")
