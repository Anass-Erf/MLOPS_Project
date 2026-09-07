import copy

import numpy as np
import pytest

from src.data.preprocess import NAMES, UNITS, normalize_payload
from src.data.validate_data import validate_soil, validate_target, validate_weather


@pytest.mark.parametrize(
    "column,value",
    [
        ("precipitation", -1),
        ("humidity", 101),
        ("temperature", 99),
        ("wind_speed", -1),
        ("solar_radiation", -1),
        ("temperature", np.nan),
        ("humidity", np.inf),
        ("temperature_min", 24),
    ],
)
def test_invalid_weather(weather, column, value):
    weather.loc[1, column] = value
    with pytest.raises(ValueError):
        validate_weather(weather)


def test_schema_duplicates_and_gaps(weather):
    validate_weather(weather)
    for bad in [weather.drop(columns="humidity"), weather.iloc[[0, 0]], weather.drop(index=10)]:
        with pytest.raises(ValueError):
            validate_weather(bad)


def test_soil_and_target():
    import pandas as pd

    with pytest.raises(ValueError):
        validate_soil(0.1, 0.2, 1)
    with pytest.raises(ValueError):
        validate_target(pd.Series([0.2, 1.1]))


def test_normalization_and_units(weather, cfg):
    row = weather.iloc[0]
    payload = {
        "properties": {"parameter": {k: {"20201101": float(row[v])} for k, v in NAMES.items()}},
        "header": {"fill_value": -999},
        "parameters": {k: {"units": v} for k, v in UNITS.items()},
    }
    payload["parameters"]["ALLSKY_SFC_SW_DWN"] = {"units": "kW-hr/m^2/day"}
    before = copy.deepcopy(payload)
    out = normalize_payload(payload, cfg["data"]["sites"][0])
    assert out.solar_radiation.iloc[0] == 54
    assert payload == before
    payload["parameters"]["T2M"]["units"] = "K"
    with pytest.raises(ValueError, match="units"):
        normalize_payload(payload, cfg["data"]["sites"][0])
