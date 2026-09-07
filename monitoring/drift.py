"""Dependency-light drift diagnostics, quality counts and delayed-label MAE checks."""

import argparse
import html
import json

import numpy as np
import pandas as pd
from scipy.stats import ks_2samp

from src.data.validate_data import WEATHER_BOUNDS
from src.features.build_features import FEATURES
from src.models.common import metrics, read_dataset
from src.models.predict import Predictor
from src.utils.config import get_path, load_config
from src.utils.logger import get_logger
from src.utils.provenance import write_json


def psi(reference: np.ndarray, current: np.ndarray) -> float:
    """Reference quantile bins, with explicit tails and constant-feature support."""
    interior = np.unique(np.quantile(reference, np.linspace(0, 1, 11)))
    if len(interior) == 1:
        value = interior[0]
        epsilon = max(abs(value) * 1e-6, 1e-6)
        interior = np.array([value - epsilon, value + epsilon])
    edges = np.r_[-np.inf, interior, np.inf]
    a = np.histogram(reference, bins=edges)[0].astype(float) + 0.5
    b = np.histogram(current, bins=edges)[0].astype(float) + 0.5
    a, b = a / a.sum(), b / b.sum()
    return float(np.sum((b - a) * np.log(b / a)))


def compare(reference: pd.DataFrame, current: pd.DataFrame, settings: dict) -> dict:
    report = {
        "reference_rows": len(reference),
        "current_rows": len(current),
        "missing_columns": [],
        "features": {},
        "performance": {"status": "labels_unavailable"},
    }
    for column in [*FEATURES, "prediction"]:
        if column not in current:
            report["missing_columns"].append(column)
            continue
        raw = pd.to_numeric(current[column], errors="coerce")
        finite = np.isfinite(raw)
        bounds = WEATHER_BOUNDS.get(column, (0, 1) if column == "prediction" else None)
        invalid = finite & ~raw.between(*bounds) if bounds else pd.Series(False, index=raw.index)
        a = pd.to_numeric(reference[column], errors="coerce").to_numpy(dtype=float)
        a = a[np.isfinite(a)]
        b = raw[finite & ~invalid].to_numpy(dtype=float)
        entry = {"missing_or_nonfinite": int((~finite).sum()), "invalid_range": int(invalid.sum())}
        if min(len(a), len(b)) < settings["min_samples"]:
            entry["status"] = "insufficient_data"
        else:
            distance = float(ks_2samp(a, b).statistic)
            divergence = psi(a, b)
            entry.update(
                {
                    "status": "compared",
                    "psi": divergence,
                    "ks_statistic": distance,
                    "drift": divergence > settings["psi_threshold"]
                    or distance > settings["ks_threshold"],
                }
            )
        report["features"][column] = entry
    if {"target", "prediction"}.issubset(current):
        valid = current.target.between(0, 1) & current.prediction.between(0, 1)
        labeled = current.loc[valid]
        report["performance"] = {
            "status": "insufficient_labels",
            "valid_labels": len(labeled),
            "invalid_or_missing_labels": int((~valid).sum()),
        }
        if len(labeled) >= settings["min_samples"]:
            baseline = metrics(reference.target, reference.prediction)
            observed = metrics(labeled.target, labeled.prediction)
            ratio = observed["mae"] / max(baseline["mae"], 1e-8)
            report["performance"].update(
                {
                    "status": "compared",
                    "reference": baseline,
                    "current": observed,
                    "mae_ratio": ratio,
                    "degradation_alert": ratio > settings["mae_ratio_threshold"],
                }
            )
    report["drift_alert"] = any(x.get("drift", False) for x in report["features"].values())
    report["quality_alert"] = bool(report["missing_columns"]) or any(
        x["missing_or_nonfinite"] or x["invalid_range"] for x in report["features"].values()
    )
    report["caveats"] = (
        "Thresholds are demonstration heuristics, not significance tests. "
        "Autocorrelation, seasonality and site mixture affect drift. "
        "Historical labels are modeled proxies; live field labels require a join."
    )
    return report


def write_html(path, report):
    rows = "".join(
        "<tr><td>" + html.escape(name) + "</td><td>" + html.escape(json.dumps(value)) + "</td></tr>"
        for name, value in report["features"].items()
    )
    path.write_text(
        "<!doctype html><html lang='en'><meta charset='utf-8'>"
        "<title>Crop water stress monitoring</title><style>"
        "body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px}"
        "td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}"
        "pre{white-space:pre-wrap;background:#f1f5f7;padding:20px}</style>"
        "<h1>Crop water stress monitoring</h1><p>"
        + html.escape(report["scenario"])
        + "</p><pre>"
        + html.escape(json.dumps({k: v for k, v in report.items() if k != "features"}, indent=2))
        + "</pre><table><tr><th>Feature</th><th>Diagnostics</th></tr>"
        + rows
        + "</table></html>"
    )


def main(events_path: str | None = None):
    cfg = load_config()
    reference = pd.read_csv(get_path(cfg, "artifacts") / "monitoring_reference.csv")
    output = get_path(cfg, "monitoring")
    output.mkdir(exist_ok=True)
    if events_path:
        events = [json.loads(line) for line in open(events_path) if line.strip()]
        current = pd.DataFrame(
            [
                {**e["features"], "prediction": e["prediction"]}
                for e in events
                if e.get("event") == "prediction"
            ]
        )
        report = compare(reference, current, cfg["monitoring"])
        report["invalid_requests"] = sum(e.get("event") == "invalid_input" for e in events)
        report["scenario"] = (
            "Actual API events; labels not joined. Group by model/site/season in practice."
        )
        write_json(output / "live_report.json", report)
        write_html(output / "live_report.html", report)
        return
    predictor = Predictor(get_path(cfg, "models") / "production.json")
    df, _ = read_dataset(cfg)
    production = df.loc[df.split == "test"].copy()
    production["prediction"] = predictor.model.predict(production[FEATURES])
    historical = compare(reference, production, cfg["monitoring"])
    historical["scenario"] = (
        "Historical held-out test vs validation; genuine weather, modeled labels. "
        "Reference predictions precede the train+validation refit."
    )
    simulated = reference.sample(n=min(400, len(reference)), random_state=cfg["seed"]).copy()
    simulated = simulated.reset_index(drop=True).drop(columns="target")
    # Deliberate feature-space perturbation, not a physically consistent climate simulation.
    for column in ("temperature", "temperature_min", "temperature_max"):
        simulated[column] += 6
    simulated["humidity"] = (simulated.humidity - 20).clip(0, 100)
    simulated["rainfall_30d"] *= 0.3
    simulated["prediction"] = predictor.model.predict(simulated[FEATURES])
    simulated.loc[:7, "humidity"] = np.nan
    simulated.loc[8:12, "precipitation"] = -1
    synthetic = compare(reference, simulated, cfg["monitoring"])
    synthetic["scenario"] = (
        "SIMULATED feature-space shift with injected invalid/missing inputs; "
        "no labels and no performance claims for counterfactual weather."
    )
    for name, report in [("historical_report", historical), ("simulated_report", synthetic)]:
        write_json(output / f"{name}.json", report)
        write_html(output / f"{name}.html", report)
    get_logger(__name__).info("Wrote historical and simulated monitoring reports to %s", output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--events", help="Optional API JSONL event log instead of demonstration data"
    )
    main(parser.parse_args().events)
