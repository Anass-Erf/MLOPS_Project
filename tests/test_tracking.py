"""Remote tracking must not register client-local artifact paths."""

from unittest.mock import Mock

import pytest

from src.models import common


@pytest.mark.parametrize("remote", [False, True])
def test_tracking_artifact_location(monkeypatch, tmp_path, cfg, remote):
    monkeypatch.setattr(common, "ROOT", tmp_path)
    tracking = Mock()
    tracking.get_experiment_by_name.return_value = None
    monkeypatch.setattr(common, "mlflow", tracking)
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    if remote:
        monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    common.setup_tracking(cfg)
    assert (tmp_path / "mlruns").exists() is not remote
    if remote:
        tracking.set_tracking_uri.assert_called_once_with("http://mlflow:5000")
        tracking.create_experiment.assert_called_once_with(cfg["tracking"]["experiment"])
    else:
        tracking.create_experiment.assert_called_once_with(
            cfg["tracking"]["experiment"],
            artifact_location=(tmp_path / "mlruns/artifacts").as_uri(),
        )
