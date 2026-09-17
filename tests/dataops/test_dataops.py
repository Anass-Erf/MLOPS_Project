"""Real offline integration plus deliberately corrupted copies, never training data."""

import copy
import json
import shutil
import subprocess

import pandas as pd
import pytest

duckdb = pytest.importorskip("duckdb")
pytest.importorskip("dlt")
pytest.importorskip("dagster")

from dagster import Definitions  # noqa: E402

from src.data.collect_data import snapshot_paths  # noqa: E402
from src.dataops.contract import COLUMNS, quality, validate_contract  # noqa: E402
from src.dataops.dbt_runner import run_dbt  # noqa: E402
from src.dataops.definitions import TrainingConsent, defs, train_model  # noqa: E402
from src.dataops.dlt_pipeline import ingest, source_frame  # noqa: E402
from src.utils.config import load_config  # noqa: E402
from src.utils.provenance import file_hash  # noqa: E402


@pytest.fixture
def config():
    return load_config()


@pytest.fixture
def canonical(config):
    return source_frame(config)[COLUMNS].copy()


@pytest.mark.parametrize(
    "damage",
    [
        "missing_column",
        "null",
        "duplicate",
        "gap",
        "missing_site",
        "unknown_site",
        "humidity",
        "rain",
        "temperature_order",
        "numeric_type",
        "date_type",
        "static_soil",
        "radiation",
        "infinite",
    ],
)
def test_contract_rejects_damage(config, canonical, damage):
    frame = canonical
    if damage == "missing_column":
        frame = frame.drop(columns="humidity")
    elif damage == "null":
        frame.loc[0, "humidity"] = float("nan")
    elif damage == "duplicate":
        frame = pd.concat([frame.iloc[:1], frame], ignore_index=True)
    elif damage == "gap":
        frame = frame.drop(index=10)
    elif damage == "missing_site":
        frame = frame.loc[frame.site_id != "meknes"]
    elif damage == "unknown_site":
        frame["site_id"] = frame.site_id.replace("meknes", "unknown")
    elif damage == "humidity":
        frame.loc[0, "humidity"] = 101
    elif damage == "rain":
        frame.loc[0, "precipitation"] = -1
    elif damage == "temperature_order":
        frame.loc[0, "temperature_min"] = frame.loc[0, "temperature"] + 1
    elif damage == "numeric_type":
        frame["humidity"] = frame.humidity.astype(str)
    elif damage == "date_type":
        frame["date"] = frame.date.astype(str)
    elif damage == "static_soil":
        frame.loc[0, "field_capacity"] = 0.99
    elif damage == "radiation":
        frame.loc[0, "solar_radiation"] = -1
    else:
        frame.loc[0, "temperature"] = float("inf")
    with pytest.raises(ValueError):
        validate_contract(frame, config)


def test_real_ingestion_dbt_contract_and_failure_gates(config, tmp_path, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("DataOps CI must not call NASA")

    monkeypatch.setattr("requests.Session.request", no_network)
    db = tmp_path / "weather.duckdb"
    first = ingest(config, db, tmp_path / "dlt")
    second = ingest(config, db, tmp_path / "dlt")
    assert first["rows"] == second["rows"] == 10407
    assert first["load_ids"] != second["load_ids"]
    with duckdb.connect(str(db), read_only=True) as con:
        assert con.sql("select count(*) from raw.raw_weather").fetchone()[0] == 10407
    run_dbt("debug", config, db)
    run_dbt("build", config, db)
    output = tmp_path / "weather.csv"
    assert quality(config, db, output)["canonical_equivalence"] == "exact"
    reference = source_frame(config)[COLUMNS]
    assert output.read_text() == reference.to_csv(index=False, date_format="%Y-%m-%d")
    approved_hash = file_hash(output)

    # Simultaneous deliberate corruption proves dbt tests actually reject data.
    with duckdb.connect(str(db)) as con:
        con.execute(
            "insert into weather_analytics.ml_weather "
            "select * from weather_analytics.ml_weather limit 1"
        )
        con.execute(
            "update weather_analytics.ml_weather set humidity=101, precipitation=-1, "
            "temperature_min=temperature+1 where date='2015-01-02'"
        )
        con.execute(
            "update weather_analytics.ml_weather set wind_speed=null where date='2015-01-03'"
        )
        con.execute(
            "update weather_analytics.ml_weather set site_id='unknown' where date='2015-01-04'"
        )
    with pytest.raises(subprocess.CalledProcessError):
        run_dbt("test", config, db)
    results = json.loads((tmp_path / "dbt_target/run_results.json").read_text())["results"]
    failed = [r["unique_id"] for r in results if r["status"] == "fail"]
    for name in [
        "weather_rules",
        "unique_site_date",
        "complete_dates",
        "not_null_ml_weather_wind_speed",
        "accepted_values_ml_weather_site_id",
    ]:
        assert any(name in test for test in failed), failed
    with pytest.raises(ValueError):
        quality(config, db, output)
    assert file_hash(output) == approved_hash  # no partial/invalid CSV publication

    run_dbt("run", config, db)
    quality(config, db, output)
    with duckdb.connect(str(db)) as con:
        con.execute("update weather_staging.stg_weather set snapshot_sha256='tampered'")
    with pytest.raises(AssertionError):
        quality(config, db, output)


@pytest.mark.parametrize("damage", ["bytes", "request", "missing_manifest"])
def test_snapshot_integrity(config, tmp_path, damage):
    cfg = copy.deepcopy(config)
    cfg["paths"]["raw"] = str(tmp_path)
    for site in cfg["data"]["sites"]:
        raw, manifest = snapshot_paths(config, site)
        shutil.copy(raw, tmp_path / raw.name)
        shutil.copy(manifest, tmp_path / manifest.name)
    raw, manifest = snapshot_paths(cfg, cfg["data"]["sites"][0])
    if damage == "bytes":
        raw.write_text("{}")
    elif damage == "request":
        meta = json.loads(manifest.read_text())
        meta["request"]["latitude"] = 0
        manifest.write_text(json.dumps(meta))
    else:
        manifest.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        source_frame(cfg)


def test_dagster_jobs_and_training_opt_in():
    Definitions.validate_loadable(defs)
    demo = defs.resolve_job_def("dataops_demo")
    assert set(demo.graph.node_names()) == {
        "ingest_weather",
        "dbt_transform",
        "data_quality",
        "build_features",
    }
    training = defs.resolve_job_def("train_evaluate_explicit")
    assert set(training.graph.node_names()) == {"train_model", "evaluate_model"}
    with pytest.raises(ValueError, match="explicit"):
        train_model(TrainingConsent())


def test_ml_paths_and_tracking_are_separate():
    from src.dataops.settings import ml_config

    original, isolated = load_config(), ml_config()
    for name in ("interim", "processed", "artifacts", "models", "monitoring"):
        assert isolated["paths"][name] != original["paths"][name]
    assert isolated["tracking"] != original["tracking"]
    for section in ("data", "features", "proxy", "split", "models"):
        assert isolated[section] == original[section]


def test_ml_rejects_stale_features_before_importing_training(tmp_path, monkeypatch):
    from src.dataops import ml_bridge

    weather = tmp_path / "weather.csv"
    weather.write_text("approved weather")
    (tmp_path / "quality.json").write_text(
        json.dumps({"status": "passed", "weather_sha256": file_hash(weather)})
    )
    (tmp_path / "dataset_manifest.json").write_text(json.dumps({"weather_sha256": "old"}))
    monkeypatch.setattr(ml_bridge, "workspace", lambda: tmp_path)
    monkeypatch.setattr(
        ml_bridge,
        "ml_config",
        lambda: {"paths": {"interim": str(weather), "artifacts": str(tmp_path)}},
    )
    with pytest.raises(ValueError, match="older weather"):
        ml_bridge.execute("train")
