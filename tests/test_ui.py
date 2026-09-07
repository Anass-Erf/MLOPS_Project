"""Client contract and interaction checks without trained artifacts or external services."""

import json
from unittest.mock import Mock

import pytest
import requests
from streamlit.testing.v1 import AppTest

from ui import utils


def test_example_and_edited_history():
    payload = utils.load_example()
    assert (payload["crop"], payload["site_id"]) == ("wheat", "marrakech")
    frame = utils.history_frame(payload)
    assert len(frame) == 30
    assert str(frame.date.iloc[0]) == "2022-10-17"
    assert str(frame.date.iloc[-1]) == "2022-11-15"
    assert utils.request_from_frame("wheat", "marrakech", frame) == payload
    frame.loc[0, "humidity"] = 50.5
    edited = utils.request_from_frame("wheat", "marrakech", frame)
    assert edited["history"][0]["humidity"] == 50.5
    assert edited["history"][1:] == payload["history"][1:]
    json.dumps(edited, allow_nan=False)


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda p: p.pop("history"), "Missing required field: history"),
        (lambda p: p["history"].pop(), "at least 30"),
        (lambda p: p.update(site_id="paris"), "site_id"),
        (lambda p: p["history"][0].update(date="bad-date"), "date"),
        (lambda p: p["history"][1].update(date=p["history"][0]["date"]), "consecutive"),
        (lambda p: p["history"][0].update(humidity=float("nan")), "finite"),
        (lambda p: p["history"][0].update(temperature_min=50), "temperature_min"),
    ],
)
def test_invalid_request(mutation, message):
    payload = utils.load_example()
    mutation(payload)
    with pytest.raises(utils.UIError, match=message):
        utils.validate_request(payload)


def test_invalid_json_and_missing_file(tmp_path):
    with pytest.raises(utils.UIError, match="Invalid JSON"):
        utils.parse_request(b"{broken")
    with pytest.raises(utils.UIError, match="Cannot read"):
        utils.load_example(tmp_path / "missing.json")
    with pytest.raises(utils.UIError):
        utils.parse_request("[]")


@pytest.fixture
def api_response():
    return {
        "prediction": 0.8,
        "stress_level": "high",
        "forecast_date": "2022-11-16",
        "model_version": "test-version",
        "unit": "test unit",
        "target": "test target",
    }


def test_prediction_http_contract(monkeypatch, api_response):
    post = Mock(return_value=Mock(status_code=200, ok=True, json=lambda: api_response))
    monkeypatch.setattr(utils.requests, "post", post)
    payload = utils.load_example()
    response = utils.predict("http://localhost:8000/", payload)
    assert response.model_dump(mode="json") == api_response
    post.assert_called_once_with("http://localhost:8000/predict", json=payload, timeout=(3, 30))
    post.return_value.json = lambda: {"prediction": 0.5}
    with pytest.raises(utils.UIError, match="Unexpected prediction response"):
        utils.predict("http://localhost:8000", payload)


@pytest.mark.parametrize(
    "exception, message",
    [(requests.ConnectionError(), "Cannot connect"), (requests.Timeout(), "timed out")],
)
def test_transport_failure(monkeypatch, exception, message):
    monkeypatch.setattr(utils.requests, "get", Mock(side_effect=exception))
    with pytest.raises(utils.UIError, match=message):
        utils.check_health("http://localhost:8000")


@pytest.mark.parametrize(
    "status, body, message",
    [
        (422, {"detail": "Outside wheat season"}, "Outside wheat season"),
        (422, {"detail": [{"loc": ["body", "history"], "type": "missing"}]}, "history"),
        (503, {}, "production model is unavailable"),
        (500, {}, "HTTP 500"),
        (200, [], "Unexpected health response"),
    ],
)
def test_api_errors(monkeypatch, status, body, message):
    monkeypatch.setattr(
        utils.requests,
        "get",
        Mock(return_value=Mock(status_code=status, ok=status < 400, json=lambda: body)),
    )
    with pytest.raises(utils.UIError, match=message):
        utils.check_health("http://localhost:8000")


def test_non_json_response(monkeypatch):
    response = Mock(status_code=200, ok=True)
    response.json.side_effect = ValueError()
    monkeypatch.setattr(utils.requests, "get", Mock(return_value=response))
    with pytest.raises(utils.UIError, match="expected JSON"):
        utils.check_health("http://localhost:8000")


def click(app, label):
    return next(button for button in app.button if button.label == label).click().run()


def test_ui_workflow_and_stale_result(monkeypatch, api_response):
    monkeypatch.setattr(
        utils.requests,
        "get",
        Mock(
            return_value=Mock(
                status_code=200,
                ok=True,
                json=lambda: {"status": "ok", "model_version": "test-version"},
            )
        ),
    )
    post = Mock(return_value=Mock(status_code=200, ok=True, json=lambda: api_response))
    monkeypatch.setattr(utils.requests, "post", post)
    app = AppTest.from_file(str(utils.EXAMPLE_PATH.parents[1] / "ui/app.py")).run()
    click(app, "Load Example")
    assert not app.exception
    assert app.selectbox(key="site").value == "marrakech"
    click(app, "Predict Water Stress")
    assert not app.exception
    assert any(metric.value == "0.800" for metric in app.metric)
    assert post.call_args.kwargs["json"] == utils.load_example()
    app.selectbox(key="site").select("meknes").run()
    assert not any(metric.label == "Stress score" for metric in app.metric)
    monkeypatch.setattr(utils.requests, "get", Mock(side_effect=requests.ConnectionError()))
    monkeypatch.setattr(utils.requests, "post", Mock(side_effect=requests.ConnectionError()))
    click(app, "Predict Water Stress")
    assert not app.exception
    assert any("Cannot connect" in error.value for error in app.error)
    assert any("API: Unavailable" in caption.value for caption in app.caption)
