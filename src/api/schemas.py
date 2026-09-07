"""Raw daily observations avoid asking API users to reproduce feature engineering."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WeatherDay(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    date: date
    temperature: float = Field(ge=-60, le=60, description="Daily mean, degrees Celsius")
    temperature_max: float = Field(ge=-60, le=65)
    temperature_min: float = Field(ge=-70, le=60)
    precipitation: float = Field(ge=0, le=1000, description="mm/day")
    humidity: float = Field(ge=0, le=100, description="Relative humidity, percent")
    wind_speed: float = Field(ge=0, le=75, description="2 m wind, m/s")
    solar_radiation: float = Field(ge=0, le=50, description="MJ/m2/day")

    @model_validator(mode="after")
    def check_temperatures(self):
        if not self.temperature_min <= self.temperature <= self.temperature_max:
            raise ValueError("Require temperature_min <= temperature <= temperature_max")
        return self


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    crop: Literal["wheat"] = "wheat"
    site_id: Literal["meknes", "settat", "marrakech"]
    history: list[WeatherDay] = Field(
        min_length=30,
        max_length=30,
        description="30 consecutive daily observations, oldest first, through forecast origin",
    )

    @model_validator(mode="after")
    def check_dates(self):
        for previous, current in zip(self.history[:-1], self.history[1:], strict=True):
            if (current.date - previous.date).days != 1:
                raise ValueError("history dates must be ordered, unique and consecutive")
        return self


class PredictionResponse(BaseModel):
    prediction: float = Field(ge=0, le=1)
    model_version: str
    forecast_date: date
    unit: str = "dimensionless (0=no modeled stress, 1=maximum modeled stress)"
    stress_level: Literal["low", "medium", "high"]
    target: str = "next_day_1_minus_Ks_proxy"
