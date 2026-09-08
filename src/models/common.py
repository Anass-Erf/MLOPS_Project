"""Dataset contracts, tracking setup, and metrics shared across model stages."""

import json
import os
from urllib.parse import urlsplit

import mlflow
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from src.features.build_features import FEATURES, assign_split
from src.utils.config import ROOT, get_path
from src.utils.provenance import file_hash, object_hash


def read_dataset(cfg: dict) -> tuple[pd.DataFrame, dict]:
    path = get_path(cfg, "processed")
    manifest = json.loads((get_path(cfg, "artifacts") / "dataset_manifest.json").read_text())
    if manifest["dataset_sha256"] != file_hash(path):
        raise ValueError("Processed dataset has changed: rebuild the features and manifest")
    if manifest["config_sha256"] != object_hash(cfg):
        raise ValueError("Configuration has changed: rebuild the pipeline")
    df = pd.read_csv(path, parse_dates=["date", "target_date"])
    if not df.target_date.sub(df.date).eq(pd.Timedelta(days=1)).all():
        raise ValueError("Every label must refer to the day after the forecast origin")
    if not (df.split == assign_split(df.target_date, cfg)).all():
        raise ValueError("Invalid chronological split assignment")
    if df[FEATURES + ["target"]].isna().any().any():
        raise ValueError("Incomplete model inputs")
    return df, manifest


def metrics(y, predictions) -> dict:
    return {
        "mae": float(mean_absolute_error(y, predictions)),
        "rmse": float(mean_squared_error(y, predictions) ** 0.5),
        "r2": float(r2_score(y, predictions)),
    }


def setup_tracking(cfg: dict) -> None:
    folder = ROOT / "mlruns"
    uri = os.environ.get("MLFLOW_TRACKING_URI", f"sqlite:///{folder / 'mlflow.db'}")
    remote = urlsplit(uri).scheme in {"http", "https"}
    if not remote:
        folder.mkdir(exist_ok=True)
    mlflow.set_tracking_uri(uri)
    experiment = cfg["tracking"]["experiment"]
    if mlflow.get_experiment_by_name(experiment) is None:
        # HTTP tracking lets the server choose its proxied artifact destination.
        # A client-local file URI cannot be used by a remote MLflow server.
        if remote:
            mlflow.create_experiment(experiment)
        else:
            mlflow.create_experiment(experiment, artifact_location=(folder / "artifacts").as_uri())
    mlflow.set_experiment(experiment)
