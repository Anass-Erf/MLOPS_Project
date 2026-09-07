"""Small artificial fixtures test mechanics only; never used for reported results."""

import joblib
import numpy as np
import pandas as pd
import pytest

from src.features.build_features import FEATURES, weather_features
from src.models.estimators import candidates
from src.utils.config import load_config
from src.utils.provenance import file_hash, write_json


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def weather():
    n = 90
    return pd.DataFrame(
        {
            "date": pd.date_range("2020-11-01", periods=n),
            "site_id": "test",
            "temperature": 18 + np.sin(np.arange(n) / 5),
            "temperature_max": 25.0,
            "temperature_min": 10.0,
            "precipitation": np.where(np.arange(n) % 8 == 0, 12.0, 0.0),
            "humidity": 60.0,
            "wind_speed": 2.0,
            "solar_radiation": 15.0,
            "latitude": 33.89,
            "longitude": -5.55,
            "field_capacity": 0.30,
            "wilting_point": 0.15,
        }
    )


@pytest.fixture
def model_artifact(tmp_path, cfg, weather):
    weather["site_id"] = "meknes"
    features = weather_features(weather, cfg).dropna(subset=FEATURES)
    # Controlled fixture labels exercise inference, not scientific performance.
    y = np.linspace(0, 1, len(features))
    model = candidates(cfg)["ridge"].fit(features[FEATURES], y)
    path = tmp_path / "model.joblib"
    joblib.dump(
        {
            "model": model,
            "metadata": {"model_version": "fixture-v1", "config": cfg, "features": FEATURES},
        },
        path,
    )
    pointer = tmp_path / "production.json"
    write_json(
        pointer,
        {"model_file": "model.joblib", "model_version": "fixture-v1", "sha256": file_hash(path)},
    )
    history = weather.tail(30)[
        [
            "date",
            "temperature",
            "temperature_max",
            "temperature_min",
            "precipitation",
            "humidity",
            "wind_speed",
            "solar_radiation",
        ]
    ].copy()
    history["date"] = history.date.dt.strftime("%Y-%m-%d")
    request = {"site_id": "meknes", "crop": "wheat", "history": history.to_dict("records")}
    return pointer, request, features.iloc[[-1]][FEATURES]
