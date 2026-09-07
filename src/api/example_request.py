"""Create a reproducible API request from genuine downloaded weather."""

import pandas as pd

from src.data.validate_data import WEATHER_BOUNDS
from src.utils.config import get_path, load_config
from src.utils.provenance import write_json


def main():
    cfg = load_config()
    weather = pd.read_csv(get_path(cfg, "interim"), parse_dates=["date"])
    samples = pd.read_csv(get_path(cfg, "processed"), parse_dates=["date"])
    origin = samples.loc[samples.split == "test"].iloc[0]
    history = weather.loc[(weather.site_id == origin.site_id) & (weather.date <= origin.date)].tail(
        30
    )
    history = history[["date", *WEATHER_BOUNDS]].copy()
    history["date"] = history.date.dt.strftime("%Y-%m-%d")
    write_json(
        get_path(cfg, "artifacts") / "example_request.json",
        {"crop": "wheat", "site_id": origin.site_id, "history": history.to_dict("records")},
    )


if __name__ == "__main__":
    main()
