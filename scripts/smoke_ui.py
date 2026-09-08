"""Run in the UI container: docker compose exec -T ui python < scripts/smoke_ui.py."""

import os
from datetime import date
from pathlib import Path
from unittest.mock import patch

import requests
from streamlit.testing.v1 import AppTest

from src.utils.config import load_config
from ui.utils import check_health, load_example, predict
from ui.weather import get_weather_history

api = os.environ["CWS_API_URL"]
assert check_health(api)["status"] == "ok"
assert requests.get(f"{api}/docs", timeout=10).status_code == 200
assert requests.get("http://mlflow:5000/health", timeout=10).status_code == 200
assert requests.get("http://mlflow:5000/", timeout=10).status_code == 200
expected = predict(api, load_example())
assert expected.model_version == "v4-2771746c21f7"
assert abs(expected.prediction - 0.8685826307973173) < 1e-12

app = AppTest.from_file("ui/app.py", default_timeout=30).run()


def click(label):
    next(button for button in app.button if button.label == label).click().run()
    assert not app.exception, app.exception


click("Load Example")
click("Predict Water Stress")
assert app.session_state.result == expected
app.radio[0].set_value("Automatic Weather").run()
click("Fetch Weather Data")
assert app.session_state.auto_weather.mode == "Offline cached snapshot"
click("Predict Water Stress")
assert app.session_state.result == expected

# A NASA outage must use the genuine bundled snapshot, without requiring internet.
with patch("ui.weather.collect", side_effect=RuntimeError("NASA unavailable")):
    weather = get_weather_history(
        "marrakech", date(2022, 11, 16), "wheat", load_config(), prefer_live=True
    )
assert weather.notice and weather.request == load_example()
cache = Path("data/raw/ui_weather/deployment-smoke.txt")
cache.write_text("persistent cache writable by appuser\n")
print(
    "PASS: API/docs, MLflow UI/health, manual and automatic UI predictions, "
    "NASA outage fallback, cache writes"
)
