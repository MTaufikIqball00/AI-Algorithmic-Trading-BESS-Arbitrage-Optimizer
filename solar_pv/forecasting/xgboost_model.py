"""
XGBoost Solar PV Generation Forecaster.
Includes chronological walk-forward validation, prediction interval calibration,
feature importance extraction, and honest baseline benchmark comparisons.
"""
import os
import json
import numpy as np
import pandas as pd
import xgboost as xgb
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

from ..features.engineering import PVFeatureEngineer, PV_FEATURE_COLUMNS
from .time_series import ChronologicalSplitter
from .evaluation import ForecastEvaluator
from .baseline import SolarBaselineForecaster
from ..config.defaults import PVSystemConfig


class PVXGBoostForecaster:
    """
    Industrial-grade XGBoost regressor for photovoltaic power output forecasting.
    """

    def __init__(self, config: Optional[PVSystemConfig] = None, model_dir: str = "data/models/solar_pv"):
        self.config = config or PVSystemConfig()
        self.model_dir = model_dir
        os.makedirs(self.model_dir, exist_ok=True)
        self.feature_engineer = PVFeatureEngineer(self.config)
        self.model: Optional[xgb.XGBRegressor] = None
        self.metadata: Dict[str, Any] = {}
        self.residual_std: float = 15.0 # fallback default uncertainty (kW)

    def train(
        self,
        df_raw: pd.DataFrame,
        target_col: str = "power",
        n_estimators: int = 400,
        learning_rate: float = 0.04,
        max_depth: int = 6,
        early_stopping_rounds: int = 30,
        random_seed: int = 42
    ) -> Dict[str, Any]:
        """
        Train XGBoost on chronological split:
        - 70% Train
        - 15% Validation (for early stopping)
        - 15% Out-of-Sample Test (for honest benchmark metrics)
        """
        # 1. Feature engineering
        df_feat = self.feature_engineer.engineer_features(df_raw)
        available_features = [col for col in PV_FEATURE_COLUMNS if col in df_feat.columns]
        
        # Drop warm-up lag rows (first 168 rows)
        df_clean = df_feat.dropna(subset=available_features + [target_col]).reset_index(drop=True)
        if len(df_clean) < 100:
            raise ValueError(f"Insufficient data rows ({len(df_clean)}) after lag generation for training.")

        # 2. Chronological split
        train_df, val_df, test_df = ChronologicalSplitter.train_val_test_split(df_clean)

        X_train, y_train = train_df[available_features], train_df[target_col]
        X_val, y_val = val_df[available_features], val_df[target_col]
        X_test, y_test = test_df[available_features], test_df[target_col]

        # 3. XGBoost model setup
        self.model = xgb.XGBRegressor(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=random_seed,
            n_jobs=4,
            early_stopping_rounds=early_stopping_rounds
        )

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )

        # 4. Out-of-sample test evaluation
        y_pred_test = self.model.predict(X_test)
        # Night-zero physical clamp
        if "solar_elevation_deg" in test_df.columns:
            y_pred_test = np.where(test_df["solar_elevation_deg"].values <= 0.0, 0.0, y_pred_test)
        y_pred_test = np.maximum(0.0, y_pred_test)

        residuals = y_test.values - y_pred_test
        self.residual_std = float(np.std(residuals))

        # Prediction intervals: 80% (z=1.282) and 95% (z=1.960)
        lower_80 = np.maximum(0.0, y_pred_test - 1.282 * self.residual_std)
        upper_80 = y_pred_test + 1.282 * self.residual_std

        # Model metrics
        model_metrics = ForecastEvaluator.evaluate(
            y_true=y_test.values,
            y_pred=y_pred_test,
            lower_interval_80=lower_80,
            upper_interval_80=upper_80,
            capacity_kw=self.config.rated_dc_power_kw
        )

        # Baseline comparison on the exact same out-of-sample slice
        baselines = SolarBaselineForecaster.evaluate_all_baselines(
            test_df=test_df,
            target_col=target_col,
            capacity_kw=self.config.rated_dc_power_kw
        )

        # Compute improvement over lag-24 seasonal naive
        baseline_mae = baselines["night_zero_seasonal_naive"]["mae"]
        improvement_pct = round(((baseline_mae - model_metrics["mae"]) / max(1e-4, baseline_mae)) * 100.0, 2)

        # 5. Feature importances
        importance_dict = {}
        for feat, imp in zip(available_features, self.model.feature_importances_):
            importance_dict[feat] = round(float(imp), 4)
        sorted_importances = dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))

        # 6. Save metadata and model artifact
        self.metadata = {
            "model_type": "XGBoostRegressor",
            "model_version": "solar_pv_xgb_v1.0",
            "training_timestamp": datetime.utcnow().isoformat() + "Z",
            "features_used": available_features,
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "test_samples": len(X_test),
            "metrics": model_metrics,
            "baseline_comparisons": baselines,
            "improvement_over_baseline_pct": improvement_pct,
            "prediction_interval_std_kw": round(self.residual_std, 3),
            "feature_importances": sorted_importances,
            "hyperparameters": {
                "n_estimators": n_estimators,
                "learning_rate": learning_rate,
                "max_depth": max_depth,
                "random_seed": random_seed
            }
        }

        # Save artifacts to disk
        model_file = os.path.join(self.model_dir, "solar_xgb_model.json")
        meta_file = os.path.join(self.model_dir, "solar_xgb_metadata.json")
        self.model.save_model(model_file)
        with open(meta_file, "w") as f:
            json.dump(self.metadata, f, indent=2)

        return self.metadata

    def predict(
        self,
        df_raw: pd.DataFrame,
        horizon: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Produce short-term multi-step solar power and energy predictions.
        """
        if self.model is None:
            # Try to load existing model
            model_file = os.path.join(self.model_dir, "solar_xgb_model.json")
            meta_file = os.path.join(self.model_dir, "solar_xgb_metadata.json")
            if os.path.exists(model_file) and os.path.exists(meta_file):
                self.model = xgb.XGBRegressor()
                self.model.load_model(model_file)
                with open(meta_file, "r") as f:
                    self.metadata = json.load(f)
                    self.residual_std = self.metadata.get("prediction_interval_std_kw", 15.0)
            else:
                raise RuntimeError("XGBoost PV model has not been trained yet. Call train() first.")

        df_feat = self.feature_engineer.engineer_features(df_raw)
        features = self.metadata.get("features_used", PV_FEATURE_COLUMNS)

        # Detect sampling interval dt_hours
        diffs = df_feat["dt"].diff().dt.total_seconds().dropna() if "dt" in df_feat.columns else pd.Series(dtype=float)
        median_sec = float(diffs.median()) if len(diffs) > 0 else 3600.0
        if median_sec <= 0 or np.isnan(median_sec):
            median_sec = 3600.0
        dt_hours = median_sec / 3600.0
        interval_minutes = max(1, int(round(median_sec / 60.0)))
        
        # Take the most recent 'horizon' rows
        recent_slice = df_feat.iloc[-horizon:].copy().reset_index(drop=True)
        X = recent_slice[features].fillna(0.0)

        preds = self.model.predict(X)

        # Enforce physical bounds: nighttime is zero
        if "solar_elevation_deg" in recent_slice.columns:
            preds = np.where(recent_slice["solar_elevation_deg"].values <= 0.0, 0.0, preds)
        preds = np.maximum(0.0, preds)

        results = []
        std = self.residual_std
        for i, row in recent_slice.iterrows():
            pred_p = float(preds[i])
            is_night = pred_p <= 0.001
            # Energy in interval: energy_kwh = power_kw * dt_hours
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
                "model_version": self.metadata.get("model_version", "solar_pv_xgb_v1.0")
            })

        return results
