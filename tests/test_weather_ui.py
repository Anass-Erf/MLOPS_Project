"""Automatic weather tests use fixture snapshots and mocked NASA HTTP calls only."""

import copy
import json
from datetime import date, timedelta
from unittest.mock import Mock

import pytest
import requests
from streamlit.testing.v1 import AppTest

from src.data.collect_data import request_params, snapshot_paths
from src.data.preprocess import NAMES, UNITS
from src.utils.provenance import file_hash, write_json
from ui import weather
from ui.utils import EXAMPLE_PATH, UIError, load_example


@pytest.fixture
def nasa(cfg, tmp_path):
    cfg = copy.deepcopy(cfg)
    cfg["paths"]["raw"] = str(tmp_path)
    payload = load_example()
    cfg["data"].update(start=payload["history"][0]["date"], end=payload["history"][-1]["date"])
    body = {
        "properties": {
            "parameter": {
                nasa: {row["date"].replace("-", ""): row[field] for row in payload["history"]}
                for nasa, field in NAMES.items()
            }
        },
        "parameters": {name: {"units": unit} for name, unit in UNITS.items()},
        "header": {"fill_value": -999},
    }
    body["parameters"]["ALLSKY_SFC_SW_DWN"] = {"units": "MJ/m^2/day"}
    return cfg, payload, body


def save_snapshot(cfg, body):
    site = weather.supported_sites(cfg)["marrakech"]
    raw, manifest = snapshot_paths(cfg, site)
    write_json(raw, body)
    write_json(
        manifest,
        {
            "source": "NASA POWER",
            "url": cfg["data"]["endpoint"],
            "request": request_params(cfg, site),
            "sha256": file_hash(raw),
        },
    )
    return raw, manifest


def test_site_and_window(cfg):
    assert weather.supported_sites(cfg)["marrakech"]["latitude"] == 31.63
    assert weather.history_window(date(2022, 11, 16), cfg) == (
        date(2022, 10, 17),
        date(2022, 11, 15),
    )
    with pytest.raises(UIError, match="future"):
        weather.history_window(date.today() + timedelta(days=1), cfg)
    with pytest.raises(UIError, match="valid prediction date"):
        weather.history_window("invalid", cfg)
    for site, crop in [("paris", "wheat"), ("marrakech", "corn")]:
        with pytest.raises(UIError, match="outside"):
            weather.get_weather_history(site, date(2022, 11, 16), crop, cfg)


def test_verified_cache_no_network(nasa, monkeypatch):
    cfg, payload, body = nasa
    raw, manifest = save_snapshot(cfg, body)
    before = (raw.read_bytes(), manifest.read_bytes())
    collect = Mock(side_effect=AssertionError("Offline must not call NASA"))
    monkeypatch.setattr(weather, "collect", collect)
    result = weather.get_weather_history("marrakech", date(2022, 11, 16), "wheat", cfg)
    assert result.request == payload
    assert result.mode == "Offline cached snapshot"
    collect.assert_not_called()
    assert before == (raw.read_bytes(), manifest.read_bytes())


def test_live_existing_collector_and_cache_reuse(nasa, monkeypatch):
    cfg, payload, body = nasa
    response = Mock(
        content=json.dumps(body).encode(), url=cfg["data"]["endpoint"], json=lambda: body
    )
    get = Mock(return_value=response)
    monkeypatch.setattr(requests.Session, "get", get)
    result = weather.get_weather_history("marrakech", date(2022, 11, 16), "wheat", cfg)
    assert result.request == payload
    assert result.mode == "Live"
    params = get.call_args.kwargs["params"]
    assert (params["start"], params["end"], params["time-standard"]) == (
        "20221017",
        "20221115",
        "LST",
    )
    assert params["latitude"] == weather.supported_sites(cfg)["marrakech"]["latitude"]
    assert len(list((weather.get_path(cfg, "raw") / "ui_weather").glob("*.manifest.json"))) == 1
    assert (
        weather.get_weather_history("marrakech", date(2022, 11, 16), "wheat", cfg).mode
        == "Offline cached snapshot"
    )
    assert get.call_count == 1


def test_live_failure_falls_back(nasa, monkeypatch):
    cfg, payload, body = nasa
    save_snapshot(cfg, body)
    monkeypatch.setattr(requests.Session, "get", Mock(side_effect=requests.Timeout()))
    result = weather.get_weather_history(
        "marrakech", date(2022, 11, 16), "wheat", cfg, prefer_live=True
    )
    assert result.request == payload
    assert result.mode == "Offline cached snapshot"
    assert "failed" in result.notice


@pytest.mark.parametrize("damage", ["checksum", "coordinates", "units", "missing", "dates", "fill"])
def test_bad_cache_rejected(nasa, monkeypatch, damage):
    cfg, _, body = nasa
    if damage == "units":
        body["parameters"]["T2M"]["units"] = "K"
    elif damage == "missing":
        del body["properties"]["parameter"]["RH2M"]
    elif damage == "dates":
        for values in body["properties"]["parameter"].values():
            values.pop("20221017")
    elif damage == "fill":
        body["properties"]["parameter"]["RH2M"]["20221017"] = -999
    raw, manifest = save_snapshot(cfg, body)
    if damage == "checksum":
        raw.write_text("{}")
    elif damage == "coordinates":
        meta = json.loads(manifest.read_text())
        meta["request"]["latitude"] = 0
        write_json(manifest, meta)
    monkeypatch.setattr(requests.Session, "get", Mock(side_effect=requests.ConnectionError()))
    with pytest.raises(UIError, match="Manual / File"):
        weather.get_weather_history("marrakech", date(2022, 11, 16), "wheat", cfg)


@pytest.mark.parametrize("failure", [requests.Timeout(), requests.HTTPError(), ValueError()])
def test_no_cache_live_failure(nasa, monkeypatch, failure):
    cfg, _, _ = nasa
    monkeypatch.setattr(requests.Session, "get", Mock(side_effect=failure))
    with pytest.raises(UIError, match="no verified local snapshot"):
        weather.get_weather_history("marrakech", date(2022, 11, 16), "wheat", cfg)


def test_radiation_uses_training_conversion(nasa):
    cfg, payload, body = nasa
    body["parameters"]["ALLSKY_SFC_SW_DWN"]["units"] = "kW-hr/m^2/day"
    for key in body["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"]:
        body["properties"]["parameter"]["ALLSKY_SFC_SW_DWN"][key] /= 3.6
    save_snapshot(cfg, body)
    result = weather.get_weather_history("marrakech", date(2022, 11, 16), "wheat", cfg)
    assert [r["solar_radiation"] for r in result.request["history"]] == pytest.approx(
        [r["solar_radiation"] for r in payload["history"]]
    )


def test_both_modes_and_changed_context(nasa, monkeypatch):
    cfg, payload, body = nasa
    save_snapshot(cfg, body)
    monkeypatch.setattr("src.utils.config.load_config", lambda: cfg)
    monkeypatch.setattr(
        requests,
        "get",
        Mock(
            return_value=Mock(
                status_code=200, ok=True, json=lambda: {"status": "ok", "model_version": "fixture"}
            )
        ),
    )
    monkeypatch.setattr(weather, "collect", Mock(side_effect=RuntimeError("NASA unavailable")))
    app = AppTest.from_file(str(EXAMPLE_PATH.parents[1] / "ui/app.py")).run()
    app.radio[0].set_value("Automatic Weather").run()
    next(b for b in app.button if b.label == "Fetch Weather Data").click().run()
    assert not app.exception
    assert json.loads(app.json[0].value) == payload
    assert any("Offline cached snapshot" in s.value for s in app.success)
    app.date_input[0].set_value(date(2022, 11, 17)).run()
    assert not app.json
    next(b for b in app.button if b.label == "Fetch Weather Data").click().run()
    assert any("Manual / File" in e.value for e in app.error)
    app.radio[0].set_value("Manual / File").run()
    next(b for b in app.button if b.label == "Load Example").click().run()
    assert json.loads(app.json[0].value) == payload
    assert not app.exception
