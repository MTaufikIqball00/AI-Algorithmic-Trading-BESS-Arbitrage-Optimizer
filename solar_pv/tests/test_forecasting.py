"""
Tests for Solar PV Forecasting Pipeline.
Verifies chronological evaluation, walk-forward splitting, baselines, and model training.
"""
import pytest
import os
import pandas as pd
import numpy as np

from solar_pv.data.ingestion.synthetic import SyntheticPVGenerator
from solar_pv.forecasting.time_series import ChronologicalSplitter
from solar_pv.forecasting.evaluation import ForecastEvaluator
from solar_pv.forecasting.baseline import SolarBaselineForecaster
from solar_pv.forecasting.xgboost_model import PVXGBoostForecaster
from solar_pv.forecasting.lightgbm_model import PVLightGBMForecaster
from solar_pv.config.defaults import PVSystemConfig


@pytest.fixture(scope="module")
def sample_pv_data():
    gen = SyntheticPVGenerator(seed=42)
    # Generate 35 days of data (approx 840 hours)
    return gen.generate(days=35, freq_minutes=60)


def test_chronological_splitter_no_leakage(sample_pv_data):
    train, val, test = ChronologicalSplitter.train_val_test_split(sample_pv_data)
    # Ensure chronological order across splits
    assert train["timestamp"].iloc[-1] < val["timestamp"].iloc[0]
    assert val["timestamp"].iloc[-1] < test["timestamp"].iloc[0]
    assert len(train) + len(val) + len(test) == len(sample_pv_data)


def test_walk_forward_cross_validation(sample_pv_data):
    folds = list(ChronologicalSplitter.walk_forward_cv(
        sample_pv_data, n_splits=3, min_train_steps=300, test_steps=24
    ))
    assert len(folds) >= 2
    for train_f, test_f in folds:
        assert train_f["timestamp"].iloc[-1] < test_f["timestamp"].iloc[0]
        assert len(test_f) == 24


def test_forecast_evaluator_metrics():
    y_true = np.array([0.0, 100.0, 500.0, 800.0, 0.0])
    y_pred = np.array([0.0, 90.0, 510.0, 780.0, 0.0])
    metrics = ForecastEvaluator.evaluate(
        y_true, y_pred,
        lower_interval_80=y_pred - 30.0,
        upper_interval_80=y_pred + 30.0,
        capacity_kw=1000.0
    )
    assert metrics["mae"] == 8.0 # (0 + 10 + 10 + 20 + 0) / 5 = 40/5 = 8.0
    assert metrics["rmse"] > 0
    assert metrics["r2_score"] > 0.95
    assert metrics["picp_80_pct"] == 100.0


def test_xgboost_forecaster_training_and_baseline_comparison(sample_pv_data, tmp_path):
    forecaster = PVXGBoostForecaster(model_dir=str(tmp_path / "models"))
    metadata = forecaster.train(
        sample_pv_data,
        target_col="power",
        n_estimators=30, # fast test
        learning_rate=0.08,
        max_depth=4
    )
    assert "metrics" in metadata
    assert "baseline_comparisons" in metadata
    assert metadata["metrics"]["mae"] > 0
    # Predict
    preds = forecaster.predict(sample_pv_data, horizon=12)
    assert len(preds) == 12
    for p in preds:
        assert "predicted_power_kw" in p
        assert p["predicted_power_kw"] >= 0.0
        assert p["lower_bound_80"] <= p["upper_bound_80"]


def test_lightgbm_forecaster_training(sample_pv_data, tmp_path):
    forecaster = PVLightGBMForecaster(model_dir=str(tmp_path / "models_lgb"))
    metadata = forecaster.train(
        sample_pv_data,
        target_col="power",
        n_estimators=30,
        learning_rate=0.08,
        num_leaves=15
    )
    assert "metrics" in metadata
    assert metadata["metrics"]["mae"] > 0
    preds = forecaster.predict(sample_pv_data, horizon=12)
    assert len(preds) == 12
    assert all(p["predicted_power_kw"] >= 0.0 for p in preds)

