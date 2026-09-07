"""Select using validation only, then refit on train+validation and register a candidate."""

from datetime import datetime, timezone

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.base import clone

from src.features.build_features import FEATURES
from src.models.common import metrics, read_dataset, setup_tracking
from src.models.estimators import candidates
from src.utils.config import get_path, load_config
from src.utils.logger import get_logger
from src.utils.provenance import file_hash, object_hash, receipt, source_hash, write_json

LOG = get_logger(__name__)


def comparison_plot(y, pred, title, path):
    fig, ax = plt.subplots(figsize=(5, 4))
    ax.scatter(y, pred, alpha=0.3, s=10)
    ax.plot([0, 1], [0, 1], "k--")
    ax.set(
        xlabel="Modeled stress label",
        ylabel="Predicted stress",
        title=title,
        xlim=(0, 1),
        ylim=(0, 1),
    )
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def train(cfg: dict) -> dict:
    df, dataset = read_dataset(cfg)
    # Model selection has no access to test arrays or test summary metrics.
    train_df = df.loc[df.split == "train"]
    validation = df.loc[df.split == "validation"]
    del df
    setup_tracking(cfg)
    artifacts = get_path(cfg, "artifacts")
    plots = artifacts / "validation"
    plots.mkdir(parents=True, exist_ok=True)
    fingerprint = object_hash(
        {"dataset": dataset["dataset_sha256"], "config": cfg, "source": source_hash()}
    )
    rows, estimators = [], candidates(cfg)
    for name, model in estimators.items():
        with mlflow.start_run(run_name=f"validation-{name}-{fingerprint[:8]}"):
            model.fit(train_df[FEATURES], train_df.target)
            predictions = model.predict(validation[FEATURES])
            scores = metrics(validation.target, predictions)
            mlflow.log_params(
                {
                    "model_type": name,
                    "seed": cfg["seed"],
                    "dataset_sha256": dataset["dataset_sha256"],
                    "train_rows": len(train_df),
                    "validation_rows": len(validation),
                    "split_strategy": "chronological_target_date",
                }
            )
            mlflow.log_dict(
                {k: str(v) for k, v in model.get_params(deep=True).items()},
                "estimator_parameters.json",
            )
            mlflow.log_dict(cfg, "config.json")
            mlflow.log_dict({"features": FEATURES}, "features.json")
            mlflow.log_dict(dataset, "dataset_manifest.json")
            mlflow.log_metrics({f"validation_{k}": v for k, v in scores.items()})
            plot = plots / f"{name}.png"
            comparison_plot(validation.target, predictions, f"Validation: {name}", plot)
            mlflow.log_artifact(str(plot))
            mlflow.sklearn.log_model(
                model,
                name="model",
                input_example=train_df[FEATURES].head(3),
                signature=infer_signature(train_df[FEATURES], model.predict(train_df[FEATURES])),
            )
            rows.append({"model": name, **scores, "run_id": mlflow.active_run().info.run_id})
            LOG.info("%s validation: %s", name, scores)
    comparison = pd.DataFrame(rows).sort_values(["rmse", "mae", "model"])
    best_name = comparison.iloc[0]["model"]
    persistence = metrics(validation.target, validation.stress_today)
    comparison.to_csv(artifacts / "model_comparison.csv", index=False)
    write_json(artifacts / "validation_persistence.json", persistence)
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(comparison.model, comparison.rmse, color="#277c8e")
    ax.axhline(persistence["rmse"], color="#ce7e19", linestyle="--", label="Stateful persistence")
    ax.set(ylabel="Validation RMSE", title="Model selection (lower is better)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(artifacts / "model_comparison.png", dpi=140)
    plt.close(fig)
    development = pd.concat([train_df, validation], ignore_index=True)
    final = clone(estimators[best_name]).fit(development[FEATURES], development.target)
    with mlflow.start_run(run_name=f"candidate-{best_name}-{fingerprint[:8]}") as run:
        mlflow.log_params(
            {
                "model_type": best_name,
                "dataset_sha256": dataset["dataset_sha256"],
                "refit_rows": len(development),
                "selection_metric": "validation_rmse",
            }
        )
        mlflow.log_dict(cfg, "config.json")
        mlflow.log_dict({"features": FEATURES}, "features.json")
        mlflow.log_dict(dataset, "dataset_manifest.json")
        mlflow.log_dict(
            {k: str(v) for k, v in final.get_params(deep=True).items()}, "estimator_parameters.json"
        )
        mlflow.log_metrics(
            {
                f"selection_validation_{k}": float(comparison.iloc[0][k])
                for k in ("mae", "rmse", "r2")
            }
        )
        mlflow.log_artifact(str(artifacts / "model_comparison.png"))
        info = mlflow.sklearn.log_model(
            final,
            name="model",
            input_example=development[FEATURES].head(3),
            signature=infer_signature(development[FEATURES], final.predict(development[FEATURES])),
        )
        version = mlflow.register_model(info.model_uri, cfg["tracking"]["registry_name"])
        MlflowClient().set_registered_model_alias(
            cfg["tracking"]["registry_name"], "candidate", version.version
        )
        model_version = f"v{version.version}-{fingerprint[:12]}"
        directory = get_path(cfg, "models") / model_version
        directory.mkdir(parents=True, exist_ok=False)
        model_path = directory / "model.joblib"
        metadata = {
            "model_version": model_version,
            "registry_version": str(version.version),
            "model_type": best_name,
            "run_id": run.info.run_id,
            "dataset_sha256": dataset["dataset_sha256"],
            "features": FEATURES,
            "config": cfg,
            "source_sha256": source_hash(),
            "fingerprint": fingerprint,
            "trained_utc": datetime.now(timezone.utc).isoformat(),
            "validation_metrics": {k: float(comparison.iloc[0][k]) for k in ("mae", "rmse", "r2")},
        }
        joblib.dump({"model": final, "metadata": metadata}, model_path)
        pointer = {
            "model_version": model_version,
            "model_file": f"{model_version}/model.joblib",
            "sha256": file_hash(model_path),
            "registry_version": str(version.version),
        }
        write_json(directory / "metadata.json", metadata)
        write_json(get_path(cfg, "models") / "candidate.json", pointer)
        write_json(
            artifacts / "selection.json",
            {
                **pointer,
                "model_type": best_name,
                "validation_metrics": metadata["validation_metrics"],
                "persistence": persistence,
                "test_used_for_selection": False,
            },
        )
    # A held-out validation reference avoids training-residual optimism in monitoring.
    reference = validation[["site_id", "date", *FEATURES, "target"]].copy()
    reference["prediction"] = estimators[best_name].predict(validation[FEATURES])
    reference.to_csv(get_path(cfg, "artifacts") / "monitoring_reference.csv", index=False)
    receipt(
        cfg,
        "train",
        [get_path(cfg, "processed")],
        [model_path, artifacts / "model_comparison.csv", artifacts / "selection.json"],
    )
    LOG.info("Registered candidate %s (%s); test remains unevaluated", model_version, best_name)
    return pointer


if __name__ == "__main__":
    train(load_config())
