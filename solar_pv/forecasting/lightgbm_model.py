"""
LightGBM Solar PV Generation Forecaster.
Fast histogram-based gradient boosted decision trees for benchmark comparison against XGBoost.
"""
import os
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

from ..features.engineering import PVFeatureEngineer, PV_FEATURE_COLUMNS
from .time_series import ChronologicalSplitter
from .evaluation import ForecastEvaluator
from .baseline import SolarBaselineForecaster
from ..config.defaults import PVSystemConfig


class PVLightGBMForecaster:
    """
    LightGBM regressor for photovoltaic power output forecasting.
    """

    def __init__(self, config: Optional[PVSystemConfig] = None, model_dir: str = "data/models/solar_pv"):
        self.config = config or PVSystemConfig()
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)
        self.feature_engineer = PVFeatureEngineer(self.config)
        self.model: Optional[lgb.LGBMRegressor] = None
        self.metadata: Dict[str, Any] = {}
        self.residual_std: float = 15.0

    def train(
        self,
        df_raw: pd.DataFrame,
        target_col: str = "power",
        n_estimators: int = 400,
        learning_rate: float = 0.04,
        num_leaves: int = 31,
        random_seed: int = 42
    ) -> Dict[str, Any]:
        """
        Train LightGBM on chronological split.
        """
        df_feat = self.feature_engineer.engineer_features(df_raw)
        available_features = [col for col in PV_FEATURE_COLUMNS if col in df_feat.columns]

        df_clean = df_feat.dropna(subset=available_features + [target_col]).reset_index(drop=True)
        if len(df_clean) < 100:
            raise ValueError("Insufficient data rows for LightGBM training.")

        train_df, val_df, test_df = ChronologicalSplitter.train_val_test_split(df_clean)

        X_train, y_train = train_df[available_features], train_df[target_col]
        X_val, y_val = val_df[available_features], val_df[target_col]
        X_test, y_test = test_df[available_features], test_df[target_col]

        self.model = lgb.LGBMRegressor(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            num_leaves=num_leaves,
            subsample=0.85,
            colsample_bytree=0.85,
            random_state=random_seed,
            n_jobs=4,
            verbosity=-1
        )

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
        )

        y_pred_test = self.model.predict(X_test)
        if "solar_elevation_deg" in test_df.columns:
            y_pred_test = np.where(test_df["solar_elevation_deg"].values <= 0.0, 0.0, y_pred_test)
        y_pred_test = np.maximum(0.0, y_pred_test)

        residuals = y_test.values - y_pred_test
        self.residual_std = float(np.std(residuals))

        lower_80 = np.maximum(0.0, y_pred_test - 1.282 * self.residual_std)
        upper_80 = y_pred_test + 1.282 * self.residual_std

        model_metrics = ForecastEvaluator.evaluate(
            y_true=y_test.values,
            y_pred=y_pred_test,
            lower_interval_80=lower_80,
            upper_interval_80=upper_80,
            capacity_kw=self.config.rated_dc_power_kw
        )

        baselines = SolarBaselineForecaster.evaluate_all_baselines(
            test_df=test_df,
            target_col=target_col,
            capacity_kw=self.config.rated_dc_power_kw
        )

        baseline_mae = baselines["night_zero_seasonal_naive"]["mae"]
        improvement_pct = round(((baseline_mae - model_metrics["mae"]) / max(1e-4, baseline_mae)) * 100.0, 2)

        self.metadata = {
            "model_type": "LightGBMRegressor",
            "model_version": "solar_pv_lgb_v1.0",
            "training_timestamp": datetime.utcnow().isoformat() + "Z",
            "features_used": available_features,
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "test_samples": len(X_test),
            "metrics": model_metrics,
            "baseline_comparisons": baselines,
            "improvement_over_baseline_pct": improvement_pct,
            "prediction_interval_std_kw": round(self.residual_std, 3)
        }

        # Save metadata and model
        model_file = os.path.join(self.model_dir, "solar_lgb_model.txt")
        meta_file = os.path.join(self.model_dir, "solar_lgb_metadata.json")
        self.model.booster_.save_model(model_file)
        with open(meta_file, "w") as f:
            json.dump(self.metadata, f, indent=2)

        return self.metadata

    def predict(
        self,
        df_raw: pd.DataFrame,
        horizon: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Produce short-term multi-step solar power and energy predictions using LightGBM.
        """
        if self.model is None:
            model_file = os.path.join(self.model_dir, "solar_lgb_model.txt")
            meta_file = os.path.join(self.model_dir, "solar_lgb_metadata.json")
            if os.path.exists(model_file) and os.path.exists(meta_file):
                booster = lgb.Booster(model_file=model_file)
                with open(meta_file, "r") as f:
                    self.metadata = json.load(f)
                    self.residual_std = self.metadata.get("prediction_interval_std_kw", 15.0)
                self._booster = booster
            else:
                raise RuntimeError("LightGBM PV model has not been trained yet. Call train() first.")

        df_feat = self.feature_engineer.engineer_features(df_raw)
        features = self.metadata.get("features_used", PV_FEATURE_COLUMNS)

        diffs = df_feat["dt"].diff().dt.total_seconds().dropna() if "dt" in df_feat.columns else pd.Series(dtype=float)
        median_sec = float(diffs.median()) if len(diffs) > 0 else 3600.0
        if median_sec <= 0 or np.isnan(median_sec):
            median_sec = 3600.0
        dt_hours = median_sec / 3600.0
        interval_minutes = max(1, int(round(median_sec / 60.0)))

        recent_slice = df_feat.iloc[-horizon:].copy().reset_index(drop=True)
        X = recent_slice[features].fillna(0.0)

        if self.model is not None:
            preds = self.model.predict(X)
        else:
            preds = self._booster.predict(X)

        if "solar_elevation_deg" in recent_slice.columns:
            preds = np.where(recent_slice["solar_elevation_deg"].values <= 0.0, 0.0, preds)
        preds = np.maximum(0.0, preds)

        results = []
        std = self.residual_std
        for i, row in recent_slice.iterrows():
            pred_p = float(preds[i])
            is_night = pred_p <= 0.001
            energy_kwh = pred_p * dt_hours

            lower_80 = 0.0 if is_night else max(0.0, pred_p - 1.282 * std)
            upper_80 = 0.0 if is_night else pred_p + 1.282 * std
            lower_95 = 0.0 if is_night else max(0.0, pred_p - 1.960 * std)
            upper_95 = 0.0 if is_night else pred_p + 1.960 * std

            results.append({
                "timestamp": str(row["timestamp"]),
                "interval_minutes": interval_minutes,
                "predicted_power_kw": round(pred_p, 2),
                "predicted_energy_kwh": round(energy_kwh, 2),
                "lower_bound_80": round(lower_80, 2),
                "upper_bound_80": round(upper_80, 2),
                "lower_bound_95": round(lower_95, 2),
                "upper_bound_95": round(upper_95, 2),
                "solar_elevation_deg": round(float(row.get("solar_elevation_deg", 0.0)), 1),
                "model_version": self.metadata.get("model_version", "solar_pv_lgb_v1.0")
            })

        return results
