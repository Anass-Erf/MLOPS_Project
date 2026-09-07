"""Serializable bounded regressors: identical clipping during scoring and serving."""

import numpy as np
from sklearn.base import BaseEstimator, RegressorMixin, clone
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


class BoundedRegressor(RegressorMixin, BaseEstimator):
    def __init__(self, estimator):
        self.estimator = estimator

    def fit(self, X, y):
        self.estimator_ = clone(self.estimator).fit(X, y)
        self.n_features_in_ = X.shape[1]
        if hasattr(X, "columns"):
            self.feature_names_in_ = np.array(X.columns)
        return self

    def predict(self, X):
        return np.clip(self.estimator_.predict(X), 0, 1)


def candidates(cfg: dict) -> dict:
    settings = cfg["models"]
    return {
        "dummy_mean": BoundedRegressor(DummyRegressor(strategy="mean")),
        "ridge": BoundedRegressor(
            make_pipeline(StandardScaler(), Ridge(alpha=settings["ridge_alpha"]))
        ),
        "random_forest": BoundedRegressor(
            RandomForestRegressor(
                n_estimators=settings["forest_trees"],
                min_samples_leaf=settings["forest_min_samples_leaf"],
                random_state=cfg["seed"],
                n_jobs=1,
            )
        ),
        "gradient_boosting": BoundedRegressor(
            HistGradientBoostingRegressor(
                max_iter=settings["boosting_iterations"],
                max_leaf_nodes=settings["boosting_max_leaf_nodes"],
                learning_rate=settings["boosting_learning_rate"],
                early_stopping=False,
                random_state=cfg["seed"],
            )
        ),
    }
