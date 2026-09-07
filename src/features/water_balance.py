"""Explicit scenario label generator, never presented as measured soil moisture."""

import numpy as np
import pandas as pd

from src.data.validate_data import validate_soil, validate_target


def crop_calendar(dates: pd.Series, proxy: dict) -> pd.DataFrame:
    dates = pd.to_datetime(dates)
    sowing = pd.to_datetime(
        {"year": dates.dt.year, "month": proxy["sowing_month"], "day": proxy["sowing_day"]}
    )
    before = dates < sowing
    sowing.loc[before] = sowing.loc[before] - pd.DateOffset(years=1)
    age = (dates - sowing).dt.days
    initial, develop, mid, late = proxy["stage_days"]
    active = age < initial + develop + mid + late
    kc = np.full(len(dates), proxy["kc_fallow"], dtype=float)
    a = age.to_numpy()
    kc[a < initial] = proxy["kc_initial"]
    mask = (a >= initial) & (a < initial + develop)
    kc[mask] = (
        proxy["kc_initial"]
        + (proxy["kc_mid"] - proxy["kc_initial"]) * (a[mask] - initial) / develop
    )
    mask = (a >= initial + develop) & (a < initial + develop + mid)
    kc[mask] = proxy["kc_mid"]
    mask = (a >= initial + develop + mid) & active.to_numpy()
    kc[mask] = (
        proxy["kc_mid"]
        + (proxy["kc_end"] - proxy["kc_mid"]) * (a[mask] - initial - develop - mid) / late
    )
    return pd.DataFrame({"crop_age": age, "active": active, "kc": kc}, index=dates.index)


def reference_et(df: pd.DataFrame) -> np.ndarray:
    """Hargreaves-Samani ET0, mm/day; FAO-56 Eq.52 with Ra converted to mm/day.

    Deliberately approximate, uncalibrated locally. Radiation/humidity/wind are ML
    covariates, not drivers of this ET0 approximation. See docs/methodology.md.
    """
    day = pd.to_datetime(df.date).dt.dayofyear.to_numpy()
    latitude = np.deg2rad(df.latitude.to_numpy())
    dr = 1 + 0.033 * np.cos(2 * np.pi * day / 365)
    declination = 0.409 * np.sin(2 * np.pi * day / 365 - 1.39)
    sunset = np.arccos(np.clip(-np.tan(latitude) * np.tan(declination), -1, 1))
    ra = (
        (24 * 60 / np.pi)
        * 0.0820
        * dr
        * (
            sunset * np.sin(latitude) * np.sin(declination)
            + np.cos(latitude) * np.cos(declination) * np.sin(sunset)
        )
    )
    return np.maximum(
        0,
        0.0023
        * (df.temperature.to_numpy() + 17.8)
        * np.sqrt(df.temperature_max - df.temperature_min)
        * 0.408
        * ra,
    )


def stress_coefficient(depletion: float, taw: float, p: float) -> float:
    return float(np.clip((taw - depletion) / ((1 - p) * taw), 0, 1))


def water_balance(weather: pd.DataFrame, proxy: dict) -> pd.DataFrame:
    """Rain first, immediate drainage, stress-limited ET, bounded end-of-day state.

    Continuous across years: no yearly wet-soil reset. Fixed root zone is an
    educational approximation; no irrigation, groundwater or measured soil input.
    """
    groups = []
    for _, group in weather.groupby("site_id", sort=True):
        g = group.copy().reset_index(drop=True)
        fc, wp = float(g.field_capacity.iloc[0]), float(g.wilting_point.iloc[0])
        root = proxy["root_depth_m"]
        validate_soil(fc, wp, root)
        taw = 1000 * (fc - wp) * root
        calendar = crop_calendar(g.date, proxy)
        et0 = reference_et(g)
        depletion = taw * proxy["initial_depletion_fraction"]
        states, stresses, actual_et, drainages = [], [], [], []
        for rain, eto, kc in zip(g.precipitation, et0, calendar.kc, strict=True):
            effective_rain = proxy["rainfall_efficiency"] * rain
            drainage = float(max(0, effective_rain - depletion))
            wet_depletion = max(0, depletion - effective_rain)
            etc = kc * eto
            p = float(np.clip(proxy["depletion_fraction"] + 0.04 * (5 - etc), 0.1, 0.8))
            aet = min(taw - wet_depletion, stress_coefficient(wet_depletion, taw, p) * etc)
            depletion = float(np.clip(wet_depletion + aet, 0, taw))
            states.append(depletion)
            stresses.append(1 - stress_coefficient(depletion, taw, p))
            actual_et.append(aet)
            drainages.append(drainage)
        g["et0"] = et0
        g["kc"] = calendar.kc
        g["active"] = calendar.active
        g["crop_age"] = calendar.crop_age
        g["depletion_mm"] = states
        g["actual_et_mm"] = actual_et
        g["drainage_mm"] = drainages
        g["modeled_soil_moisture"] = fc - g.depletion_mm / (1000 * root)
        g["stress_today"] = stresses
        validate_target(g.stress_today)
        groups.append(g)
    return pd.concat(groups, ignore_index=True)
