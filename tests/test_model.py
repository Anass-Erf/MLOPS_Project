import json

import numpy as np
import pytest

from src.api.schemas import PredictionRequest
from src.features.build_features import FEATURES, weather_features
from src.models.estimators import candidates
from src.models.predict import Predictor


def test_model_inference_parity(model_artifact):
    pointer, request, expected_features = model_artifact
    predictor = Predictor(pointer)
    response, actual_features = predictor.predict(PredictionRequest(**request))
    np.testing.assert_allclose(actual_features, expected_features, rtol=1e-12)
    assert response["prediction"] == pytest.approx(predictor.model.predict(expected_features)[0])
    assert 0 <= response["prediction"] <= 1
    assert response["model_version"] == "fixture-v1"


def test_tampered_artifact(model_artifact):
    pointer, _, _ = model_artifact
    info = json.loads(pointer.read_text())
    (pointer.parent / info["model_file"]).write_bytes(b"corrupt")
    with pytest.raises(ValueError, match="checksum"):
        Predictor(pointer)


@pytest.mark.parametrize("name", ["dummy_mean", "ridge", "random_forest", "gradient_boosting"])
def test_all_estimators_bounded(cfg, weather, name):
    features = weather_features(weather, cfg).dropna(subset=FEATURES)
    model = candidates(cfg)[name].fit(features[FEATURES], np.linspace(-0.2, 1.2, len(features)))
    assert np.isfinite(model.predict(features[FEATURES])).all()
    assert (
        (model.predict(features[FEATURES]) >= 0) & (model.predict(features[FEATURES]) <= 1)
    ).all()
