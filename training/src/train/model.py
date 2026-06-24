from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BaselineMeanModel:
    mean_price: float

    def predict(self, features):
        import numpy as np

        return np.full(len(features), self.mean_price)


def train_model(features, target, categorical_features: list[str], model_params: dict[str, Any] | None = None):
    try:
        import lightgbm as lgb

        params = _build_model_params(model_params)
        model = lgb.LGBMRegressor(**params)
        model.fit(features, target, categorical_feature=categorical_features)
        return model
    except ModuleNotFoundError:
        return BaselineMeanModel(mean_price=float(target.mean()))


def tune_model(
    train_x,
    train_y,
    valid_x,
    valid_y,
    categorical_features: list[str],
    *,
    base_params: dict[str, Any],
    n_trials: int,
    timeout_seconds: int | None,
    early_stopping_rounds: int,
) -> dict[str, Any]:
    import lightgbm as lgb
    import numpy as np
    import optuna

    def objective(trial: optuna.Trial) -> float:
        params = _build_model_params(
            {
                **base_params,
                "n_estimators": 2000,
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.08, log=True),
                "num_leaves": trial.suggest_int("num_leaves", 16, 256, log=True),
                "max_depth": trial.suggest_int("max_depth", 3, 12),
                "min_child_samples": trial.suggest_int("min_child_samples", 20, 300),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
            }
        )
        model = lgb.LGBMRegressor(**params)
        model.fit(
            train_x,
            train_y,
            categorical_feature=categorical_features,
            eval_set=[(valid_x, valid_y)],
            eval_metric="mae",
            callbacks=[
                lgb.early_stopping(early_stopping_rounds, verbose=False),
                lgb.log_evaluation(0),
            ],
        )
        predictions = model.predict(valid_x)
        mae = float(np.mean(np.abs(valid_y.to_numpy() - predictions)))
        trial.set_user_attr("best_iteration", int(model.best_iteration_ or params["n_estimators"]))
        return mae

    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=n_trials, timeout=timeout_seconds)

    best_params = _build_model_params({**base_params, **study.best_trial.params})
    best_params["n_estimators"] = int(study.best_trial.user_attrs.get("best_iteration", best_params["n_estimators"]))
    return {
        "params": best_params,
        "best_value": float(study.best_value),
        "trials": len(study.trials),
    }


def _build_model_params(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "objective": "regression",
        "n_estimators": 300,
        "learning_rate": 0.05,
        "random_state": 42,
        "verbosity": -1,
    }
    if overrides:
        params.update(overrides)
    return params
