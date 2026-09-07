import copy

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app


def test_endpoints(model_artifact, tmp_path):
    pointer, request, _ = model_artifact
    with TestClient(create_app(pointer, tmp_path / "events.jsonl")) as client:
        assert client.get("/").status_code == 200
        assert client.get("/health").json()["model_version"] == "fixture-v1"
        assert client.get("/docs").status_code == 200
        response = client.post("/predict", json=request)
        assert response.status_code == 200
        assert 0 <= response.json()["prediction"] <= 1
        assert response.json()["forecast_date"] == "2021-01-30"
    assert '"event": "prediction"' in (tmp_path / "events.jsonl").read_text()


@pytest.mark.parametrize(
    "mutation", ["rain", "missing", "short", "duplicate", "site", "extra", "order"]
)
def test_invalid_requests(model_artifact, tmp_path, mutation):
    pointer, original, _ = model_artifact
    request = copy.deepcopy(original)
    if mutation == "rain":
        request["history"][0]["precipitation"] = -1
    elif mutation == "missing":
        del request["history"][0]["humidity"]
    elif mutation == "short":
        request["history"].pop()
    elif mutation == "duplicate":
        request["history"][1]["date"] = request["history"][0]["date"]
    elif mutation == "site":
        request["site_id"] = "paris"
    elif mutation == "extra":
        request["target"] = 0.8
    else:
        request["history"][0]["temperature_min"] = 30
    with TestClient(create_app(pointer, tmp_path / "events.jsonl")) as client:
        assert client.post("/predict", json=request).status_code == 422
    assert '"event": "invalid_input"' in (tmp_path / "events.jsonl").read_text()


def test_missing_model(tmp_path):
    with TestClient(create_app(tmp_path / "missing.json", tmp_path / "events.jsonl")) as client:
        assert client.get("/").status_code == 200
        assert client.get("/health").status_code == 503


def test_out_of_season(model_artifact, tmp_path):
    import pandas as pd

    pointer, request, _ = model_artifact
    for day, timestamp in zip(
        request["history"], pd.date_range("2021-07-01", periods=30), strict=True
    ):
        day["date"] = str(timestamp.date())
    with TestClient(create_app(pointer, tmp_path / "events.jsonl")) as client:
        assert client.post("/predict", json=request).status_code == 422
