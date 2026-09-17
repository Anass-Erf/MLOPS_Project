"""Generated DataOps state is separate from existing datasets and releases."""

import copy
import os
from pathlib import Path

from src.utils.config import ROOT, load_config


def workspace() -> Path:
    path = Path(os.environ.get("CWS_DATAOPS_DIR", ROOT / "artifacts/dataops")).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def database() -> Path:
    return workspace() / "crop_water_stress.duckdb"


def ml_config() -> dict:
    cfg = copy.deepcopy(load_config())
    base = workspace()
    # Existing provenance receipts use repository-relative paths.
    base.relative_to(ROOT)
    for name, suffix in {
        "interim": "weather.csv",
        "processed": "features.csv",
        "artifacts": "ml_artifacts",
        "models": "models",
        "monitoring": "monitoring",
    }.items():
        cfg["paths"][name] = str(base / suffix)
    cfg["tracking"] = {
        "experiment": "crop-water-stress-dataops-demo",
        "registry_name": "crop-water-stress-dataops-demo",
    }
    return cfg
