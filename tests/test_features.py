import numpy as np
import pandas as pd
import pytest

from src.features.build_features import FEATURES, assign_split, weather_features
from src.features.water_balance import reference_et, stress_coefficient, water_balance


def test_stress_known_values():
    assert stress_coefficient(0, 100, 0.5) == 1
    assert stress_coefficient(50, 100, 0.5) == 1
    assert stress_coefficient(75, 100, 0.5) == 0.5
    assert stress_coefficient(100, 100, 0.5) == 0


def test_hargreaves_unit_conversion(weather):
    # FAO example Ra for 15 July at 45.72 N is approximately 40.6 MJ/m2/day.
    row = weather.iloc[:1].copy()
    row["date"] = pd.Timestamp("2021-07-15")
    row["latitude"] = 45.72
    row["temperature"] = 20.7
    row["temperature_max"] = 26.6
    row["temperature_min"] = 14.8
    expected = 0.0023 * (20.7 + 17.8) * np.sqrt(26.6 - 14.8) * 0.408 * 40.6
    assert reference_et(row).iloc[0] == pytest.approx(expected, rel=0.01)


def test_causality_and_online_parity(weather, cfg):
    full = weather_features(weather, cfg)
    changed = weather.copy()
    changed.loc[61:, "precipitation"] = 100
    pd.testing.assert_frame_equal(
        full.loc[:60, FEATURES], weather_features(changed, cfg).loc[:60, FEATURES]
    )
    online = weather_features(weather.iloc[31:61].copy(), cfg)
    np.testing.assert_allclose(
        full.loc[60, FEATURES].astype(float), online.iloc[-1][FEATURES].astype(float), rtol=1e-12
    )
    assert full.rainfall_30d.iloc[29] == weather.precipitation.iloc[:30].sum()
    assert full.rainfall_30d.iloc[:29].isna().all()
    assert not {"target", "stress_today", "depletion_mm", "modeled_soil_moisture"} & set(FEATURES)


def test_site_windows_are_isolated(weather, cfg):
    other = weather.copy()
    other["site_id"] = "second"
    other["precipitation"] = 0
    combined = weather_features(pd.concat([weather, other]), cfg)
    assert combined.loc[combined.site_id == "second", "rainfall_30d"].dropna().eq(0).all()


def test_balance_conservation_and_future_independence(weather, cfg):
    balance = water_balance(weather, cfg["proxy"])
    taw = 150
    previous = np.r_[
        taw * cfg["proxy"]["initial_depletion_fraction"], balance.depletion_mm.to_numpy()[:-1]
    ]
    expected = previous - 0.8 * weather.precipitation + balance.actual_et_mm + balance.drainage_mm
    np.testing.assert_allclose(balance.depletion_mm, expected, atol=1e-12)
    assert balance.depletion_mm.between(0, taw).all()
    changed = weather.copy()
    changed.loc[61:, "precipitation"] = 100
    pd.testing.assert_frame_equal(balance.iloc[:61], water_balance(changed, cfg["proxy"]).iloc[:61])


def test_split_uses_target_date(cfg):
    dates = pd.Series(pd.to_datetime(["2021-06-30", "2021-07-01", "2022-07-01"]))
    assert list(assign_split(dates, cfg)) == ["train", "validation", "test"]
