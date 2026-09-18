"""Dagster lineage and explicit jobs; importing these definitions performs no work."""

from dagster import (
    AssetSelection,
    AssetSpec,
    Config,
    Definitions,
    MaterializeResult,
    asset,
    define_asset_job,
)

from src.dataops.cli import run_ml
from src.dataops.contract import quality
from src.dataops.dbt_runner import run_dbt
from src.dataops.dlt_pipeline import ingest
from src.dataops.settings import database, workspace
from src.utils.config import load_config

nasa_snapshots = AssetSpec(
    "nasa_snapshots",
    description="Existing immutable NASA POWER JSON + SHA-256 manifests for all three sites.",
)


@asset(deps=[nasa_snapshots], group_name="dataops")
def ingest_weather():
    """dlt -> DuckDB raw.raw_weather; verified offline snapshots, never invented data."""
    report = ingest(load_config(), database(), workspace() / "dlt")
    return MaterializeResult(metadata={"rows": report["rows"], "table": report["table"]})


@asset(deps=[ingest_weather], group_name="dataops")
def dbt_transform():
    """dbt staging -> canonical ML weather; schema contracts + SQL data tests."""
    run_dbt("build", load_config(), database())
    return MaterializeResult(
        metadata={"models": "weather_staging.stg_weather -> weather_analytics.ml_weather"}
    )


@asset(deps=[dbt_transform], group_name="dataops")
def data_quality():
    """Fail closed on the shared Python contract and exact snapshot-equivalence check."""
    report = quality(load_config(), database(), workspace() / "weather.csv")
    return MaterializeResult(
        metadata={"rows": report["rows"], "weather_sha256": report["weather_sha256"]}
    )


@asset(deps=[data_quality], group_name="ml_demo")
def build_features():
    """Reuse existing causal features, wheat proxy and chronological splits, in isolation."""
    run_ml("features")
    return MaterializeResult(metadata={"path": str(workspace() / "features.csv")})


class TrainingConsent(Config):
    enabled: bool = False


@asset(deps=[build_features], group_name="ml_demo")
def train_model(config: TrainingConsent):
    """Explicit isolated training only; no production alias or release is changed."""
    if not config.enabled:
        raise ValueError("Choose train_evaluate_explicit to enable isolated demo training")
    run_ml("train")
    return MaterializeResult(metadata={"registry": "crop-water-stress-dataops-demo"})


@asset(deps=[train_model], group_name="ml_demo")
def evaluate_model():
    """Reuse frozen evaluation logic; no promotion asset exists."""
    run_ml("evaluate")
    return MaterializeResult(metadata={"reports": str(workspace() / "ml_artifacts/evaluation")})


demo = define_asset_job(
    "dataops_demo",
    selection=AssetSelection.assets(ingest_weather, dbt_transform, data_quality, build_features),
    description="Short offline demo, through features only. Does not train or promote.",
)
training = define_asset_job(
    "train_evaluate_explicit",
    selection=AssetSelection.assets(train_model, evaluate_model),
    config={"ops": {"train_model": {"config": {"enabled": True}}}},
    description="Run after dataops_demo. Train/evaluate in separate MLflow storage; no promotion.",
)
defs = Definitions(
    assets=[
        nasa_snapshots,
        ingest_weather,
        dbt_transform,
        data_quality,
        build_features,
        train_model,
        evaluate_model,
    ],
    jobs=[demo, training],
)
