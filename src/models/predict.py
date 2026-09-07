"""Load a verified version and reproduce the exact offline feature calculation."""

import json
from datetime import timedelta
from pathlib import Path

import joblib
import pandas as pd

from src.api.schemas import PredictionRequest
from src.features.build_features import FEATURES, weather_features
from src.features.water_balance import crop_calendar
from src.utils.provenance import file_hash


class Predictor:
    def __init__(self, pointer_path: Path):
        pointer = json.loads(pointer_path.read_text())
        model_path = pointer_path.parent / pointer["model_file"]
        if file_hash(model_path) != pointer["sha256"]:
            raise ValueError("Model artifact checksum mismatch")
        # joblib is only for trusted artifacts produced by this local project.
        bundle = joblib.load(model_path)
        self.model = bundle["model"]
        self.metadata = bundle["metadata"]
        self.cfg = self.metadata["config"]
        if self.metadata["features"] != FEATURES:
            raise ValueError("Deployed feature contract differs from model contract")
        if self.metadata["model_version"] != pointer["model_version"]:
            raise ValueError("Model version and pointer disagree")

    def prepare(self, request: PredictionRequest) -> pd.DataFrame:
        site = next((s for s in self.cfg["data"]["sites"] if s["id"] == request.site_id), None)
        if site is None:
            raise ValueError("Site is outside the trained scenario")
        weather = pd.DataFrame([day.model_dump() for day in request.history])
        weather["date"] = pd.to_datetime(weather.date)
        weather["site_id"] = request.site_id
        for key in ("latitude", "longitude", "field_capacity", "wilting_point"):
            weather[key] = site[key]
        origin = weather.date.iloc[-1]
        active = crop_calendar(
            pd.Series([origin, origin + pd.Timedelta(days=1)]), self.cfg["proxy"]
        )
        if not active.active.all():
            raise ValueError(
                "Forecast origin and target must both be in the configured wheat season"
            )
        return weather_features(weather, self.cfg).iloc[[-1]][FEATURES]

    def predict(self, request: PredictionRequest) -> tuple[dict, pd.DataFrame]:
        features = self.prepare(request)
        value = float(self.model.predict(features)[0])
        return {
            "prediction": value,
            "model_version": self.metadata["model_version"],
            "forecast_date": request.history[-1].date + timedelta(days=1),
            "stress_level": "low" if value < 0.3 else "medium" if value < 0.6 else "high",
        }, features
