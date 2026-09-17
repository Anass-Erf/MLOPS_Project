"""Explicit ML stages executed with the original application interpreter.

This module is never imported by serving. Paths and tracking are isolated even
when the caller has production MLFLOW_TRACKING_URI or CWS_CONFIG variables set.
"""

import argparse
import json
import os

from src.dataops.settings import ml_config, workspace
from src.utils.config import get_path
from src.utils.provenance import file_hash


def execute(stage: str) -> None:
    cfg = ml_config()
    base = workspace()
    approved = json.loads((base / "quality.json").read_text())
    if approved["status"] != "passed" or approved["weather_sha256"] != file_hash(
        get_path(cfg, "interim")
    ):
        raise ValueError("Weather changed after quality approval; rerun dataops-quality")
    get_path(cfg, "artifacts").mkdir(parents=True, exist_ok=True)
    if stage == "features":
        from src.features.build_features import build_features

        build_features(cfg)
    else:
        manifest = json.loads((get_path(cfg, "artifacts") / "dataset_manifest.json").read_text())
        if manifest["weather_sha256"] != approved["weather_sha256"]:
            raise ValueError("Features use older weather; rerun dataops-demo before training")
        from src.models import common
        from src.models.evaluate import evaluate
        from src.models.train import train

        # setup_tracking uses its module ROOT for local artifact storage. Rebind
        # only inside this short-lived worker, keeping original MLflow untouched.
        common.ROOT = base
        os.environ["MLFLOW_TRACKING_URI"] = f"sqlite:///{base / 'mlruns/mlflow.db'}"
        (train if stage == "train" else evaluate)(cfg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=["features", "train", "evaluate"])
    execute(parser.parse_args().stage)
