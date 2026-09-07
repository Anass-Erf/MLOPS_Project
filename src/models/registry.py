"""Promote a locally evaluated candidate; preserve immutable versions for rollback."""

import argparse
import json

from mlflow.tracking import MlflowClient

from src.models.common import setup_tracking
from src.utils.config import get_path, load_config
from src.utils.logger import get_logger
from src.utils.provenance import file_hash, write_json


def promote(cfg: dict, version: str | None = None) -> None:
    folder = get_path(cfg, "models")
    if version:
        if "/" in version or ".." in version:
            raise ValueError("Expected a model version directory name")
        path = folder / version / "model.joblib"
        meta = json.loads((path.parent / "metadata.json").read_text())
        pointer = {
            "model_version": version,
            "model_file": f"{version}/model.joblib",
            "sha256": file_hash(path),
            "registry_version": meta["registry_version"],
        }
    else:
        pointer = json.loads((folder / "candidate.json").read_text())
    report = (
        get_path(cfg, "artifacts") / "evaluation" / pointer["model_version"] / "test_metrics.json"
    )
    if not report.exists():
        raise ValueError("Candidate must have a frozen evaluation before promotion")
    if json.loads(report.read_text())["model_sha256"] != pointer["sha256"]:
        raise ValueError("Evaluation does not match candidate artifact")
    if file_hash(folder / pointer["model_file"]) != pointer["sha256"]:
        raise ValueError("Candidate artifact has changed")
    setup_tracking(cfg)
    MlflowClient().set_registered_model_alias(
        cfg["tracking"]["registry_name"], "production", pointer["registry_version"]
    )
    write_json(folder / "production.json", pointer)
    get_logger(__name__).info("Promoted %s; restart API to load it", pointer["model_version"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", help="Previously evaluated version for rollback")
    promote(load_config(), parser.parse_args().version)
