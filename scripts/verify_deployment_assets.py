"""Check the existing release without training or changing any artifacts."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.schemas import PredictionRequest  # noqa: E402
from src.models.predict import Predictor  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-only", action="store_true")
    args = parser.parse_args()
    predictor = Predictor(ROOT / "models/production.json")
    request = PredictionRequest.model_validate_json(
        (ROOT / "artifacts/example_request.json").read_text()
    )
    response, _ = predictor.predict(request)
    if not args.model_only:
        from datetime import timedelta

        from src.utils.config import load_config
        from ui.weather import get_weather_history

        cfg = load_config()
        for site in cfg["data"]["sites"]:
            weather = get_weather_history(
                site["id"], request.history[-1].date + timedelta(days=1), "wheat", cfg
            )
            assert weather.mode == "Offline cached snapshot"
        evaluation = json.loads(
            (
                ROOT / "artifacts/evaluation" / response["model_version"] / "test_metrics.json"
            ).read_text()
        )
        pointer = json.loads((ROOT / "models/production.json").read_text())
        assert evaluation["model_sha256"] == pointer["sha256"]
    print(json.dumps(response, default=str))


if __name__ == "__main__":
    main()
