from __future__ import annotations

from dataclasses import dataclass


@dataclass
class BaselineMeanModel:
    mean_price: float

    def predict(self, features):
        import numpy as np

        return np.full(len(features), self.mean_price)


def train_model(features, target, categorical_features: list[str]):
    try:
        import lightgbm as lgb

        model = lgb.LGBMRegressor(
            objective="regression",
            n_estimators=300,
            learning_rate=0.05,
            random_state=42,
        )
        model.fit(features, target, categorical_feature=categorical_features)
        return model
    except ModuleNotFoundError:
        return BaselineMeanModel(mean_price=float(target.mean()))
