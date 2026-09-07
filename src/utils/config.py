"""Central configuration; paths are independent of the shell working directory."""

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def load_config() -> dict:
    path = Path(os.environ.get("CWS_CONFIG", ROOT / "configs/config.yaml"))
    with path.open() as handle:
        cfg = yaml.safe_load(handle)
    if cfg["features"]["history_days"] != 30:
        raise ValueError("The feature contract requires exactly 30 history days")
    if not cfg["split"]["train_end"] < cfg["split"]["validation_end"] < cfg["data"]["end"]:
        raise ValueError("Split boundaries must be strictly ordered before data end")
    return cfg


def resolve(value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def get_path(cfg: dict, name: str) -> Path:
    return resolve(cfg["paths"][name])
