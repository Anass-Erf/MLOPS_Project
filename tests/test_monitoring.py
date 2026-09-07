import numpy as np
import pandas as pd

from monitoring.drift import compare, psi
from src.features.build_features import FEATURES


def test_drift_missing_and_labels(cfg):
    rng = np.random.default_rng(42)
    ref = pd.DataFrame({col: rng.uniform(0, 1, 100) for col in [*FEATURES, "prediction"]})
    ref["target"] = ref.prediction * 0.9
    cur = ref.copy()
    cur["temperature"] += 20
    cur.loc[0, "humidity"] = np.nan
    cur["target"] = 1 - cur.prediction
    report = compare(ref, cur, cfg["monitoring"])
    assert report["drift_alert"] and report["quality_alert"]
    assert report["performance"]["degradation_alert"]
    no_labels = compare(ref, cur.drop(columns=["target", "wind_speed"]), cfg["monitoring"])
    assert no_labels["performance"]["status"] == "labels_unavailable"
    assert "wind_speed" in no_labels["missing_columns"]
    assert psi(np.ones(100), np.ones(100)) == 0
    assert psi(np.ones(100), np.ones(100) * 2) > 0.2
