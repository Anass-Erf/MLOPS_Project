"""Evaluate the frozen selected candidate once per model/dataset pair."""

import json

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow

from src.features.build_features import FEATURES
from src.models.common import metrics, read_dataset, setup_tracking
from src.models.train import comparison_plot
from src.utils.config import get_path, load_config
from src.utils.logger import get_logger
from src.utils.provenance import file_hash, receipt, write_json

LOG = get_logger(__name__)


def evaluate(cfg: dict) -> dict:
    pointer = json.loads((get_path(cfg, "models") / "candidate.json").read_text())
    path = get_path(cfg, "models") / pointer["model_file"]
    if file_hash(path) != pointer["sha256"]:
        raise ValueError("Candidate model checksum mismatch")
    bundle = joblib.load(path)
    metadata = bundle["metadata"]
    df, manifest = read_dataset(cfg)
    if metadata["dataset_sha256"] != manifest["dataset_sha256"]:
        raise ValueError("Candidate was trained against a different dataset")
    report_dir = get_path(cfg, "artifacts") / "evaluation" / pointer["model_version"]
    report_path = report_dir / "test_metrics.json"
    if report_path.exists():
        cached = json.loads(report_path.read_text())
        if cached["model_sha256"] != pointer["sha256"]:
            raise ValueError("Cached evaluation model checksum mismatch")
        LOG.info("Reusing frozen test evaluation %s", report_path)
        return cached
    report_dir.mkdir(parents=True, exist_ok=True)
    test = df.loc[df.split == "test"].copy()
    predictions = bundle["model"].predict(test[FEATURES])
    scores = metrics(test.target, predictions)
    test["prediction"] = predictions
    test[["site_id", "date", "target_date", "target", "prediction", "stress_today"]].to_csv(
        report_dir / "test_predictions.csv", index=False
    )
    result = {
        "model_version": pointer["model_version"],
        "model_type": metadata["model_type"],
        "model_sha256": pointer["sha256"],
        "dataset_sha256": manifest["dataset_sha256"],
        "test_rows": len(test),
        "metrics": scores,
        "persistence_metrics": metrics(test.target, test.stress_today),
        "by_site": {name: metrics(g.target, g.prediction) for name, g in test.groupby("site_id")},
        "interpretation": "Agreement with a modeled proxy, not field accuracy",
    }
    comparison_plot(
        test.target, predictions, "Frozen model: held-out test", report_dir / "scatter.png"
    )
    fig, axes = plt.subplots(2, 1, figsize=(11, 7))
    for site, g in test.groupby("site_id"):
        axes[0].plot(g.target_date, g.prediction - g.target, linewidth=0.7, label=site)
    axes[0].set(ylabel="Prediction - proxy", title="Test residuals through time")
    axes[0].legend()
    axes[1].hist(predictions - test.target, bins=40, color="#277c8e")
    axes[1].set(xlabel="Residual", ylabel="Count")
    fig.tight_layout()
    fig.savefig(report_dir / "residuals.png", dpi=140)
    plt.close(fig)
    setup_tracking(cfg)
    with mlflow.start_run(run_id=metadata["run_id"]):
        mlflow.log_metrics({f"test_{k}": v for k, v in scores.items()})
        mlflow.log_metrics(
            {f"test_persistence_{k}": v for k, v in result["persistence_metrics"].items()}
        )
        mlflow.log_dict(result, "test_metrics.json")
        mlflow.log_artifacts(str(report_dir), artifact_path="test_evaluation")
    write_json(report_path, result)
    receipt(cfg, "evaluate", [path, get_path(cfg, "processed")], [report_path])
    LOG.info("Frozen test evaluation: %s; persistence: %s", scores, result["persistence_metrics"])
    return result


if __name__ == "__main__":
    evaluate(load_config())
