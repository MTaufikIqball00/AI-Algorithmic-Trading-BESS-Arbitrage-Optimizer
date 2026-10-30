"""
XGBoost electricity price forecaster with walk-forward chronological evaluation,
prediction intervals, and persistence baseline comparison.
"""
import os
import json
import numpy as np
import pandas as pd
import xgboost as xgb
from datetime import datetime
from typing import Dict, Any, Tuple, List
from .feature_engineering import engineer_features, FEATURE_COLUMNS

class PriceForecaster:
    def __init__(self, model_dir: str = "data/models"):
        # Resolve model_dir relative to current working directory or package location
        candidates = [
            model_dir,
            os.path.join("..", model_dir),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", model_dir),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", model_dir),
        ]
        chosen = model_dir
        for c in candidates:
            if os.path.exists(c):
                chosen = os.path.abspath(c)
                break
        self.model_dir = chosen
        os.makedirs(self.model_dir, exist_ok=True)
        self.model = None
        self.metadata = {}
        self.residual_std = 5.0 # default fallback uncertainty

    def train(self, df_raw: pd.DataFrame) -> Dict[str, Any]:
        """
        Train XGBoost on chronological split:
        - 70% Train
        - 15% Validation (for early stopping)
        - 15% Out-of-Sample Test (for honest benchmark metrics)
        """
        df_feat = engineer_features(df_raw)
        # Drop rows with NaN from lags (first 168 rows)
        df_clean = df_feat.dropna(subset=FEATURE_COLUMNS + ['price_actual']).reset_index(drop=True)
        
        n = len(df_clean)
        train_end = int(n * 0.70)
        val_end = int(n * 0.85)

        train_df = df_clean.iloc[:train_end]
        val_df = df_clean.iloc[train_end:val_end]
        test_df = df_clean.iloc[val_end:]

        X_train = train_df[FEATURE_COLUMNS]
        y_train = train_df['price_actual']

        X_val = val_df[FEATURE_COLUMNS]
        y_val = val_df['price_actual']

        X_test = test_df[FEATURE_COLUMNS]
        y_test = test_df['price_actual']

        # XGBoost Regressor
        self.model = xgb.XGBRegressor(
            n_estimators=400,
            learning_rate=0.04,
            max_depth=6,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=4,
            early_stopping_rounds=30
        )

        self.model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )

        # Evaluate on out-of-sample Test Set
        y_pred_test = self.model.predict(X_test)
        residuals = y_test.values - y_pred_test
        self.residual_std = float(np.std(residuals))

        # Test metrics
        mae = float(np.mean(np.abs(residuals)))
        rmse = float(np.sqrt(np.mean(residuals ** 2)))
        # Non-zero safe MAPE
        non_zero_mask = np.abs(y_test.values) > 1.0
        mape = float(np.mean(np.abs(residuals[non_zero_mask] / y_test.values[non_zero_mask])) * 100.0)

        # Baseline 1: Lag-1 Persistence (y_pred = price_lag_1)
        res_p1 = y_test.values - test_df['price_lag_1'].values
        mae_p1 = float(np.mean(np.abs(res_p1)))
        rmse_p1 = float(np.sqrt(np.mean(res_p1 ** 2)))

        # Baseline 2: Lag-24 Seasonal Naive (y_pred = price_lag_24)
        res_p24 = y_test.values - test_df['price_lag_24'].values
        mae_p24 = float(np.mean(np.abs(res_p24)))
        rmse_p24 = float(np.sqrt(np.mean(res_p24 ** 2)))

        # Feature importances
        importance_dict = dict(zip(FEATURE_COLUMNS, [float(x) for x in self.model.feature_importances_]))
        sorted_importance = dict(sorted(importance_dict.items(), key=lambda item: item[1], reverse=True))

        self.metadata = {
            "model_type": "XGBoost Regressor",
            "version": "1.0.0",
            "trained_at": datetime.utcnow().isoformat() + "Z",
            "samples_train": len(train_df),
            "samples_val": len(val_df),
            "samples_test": len(test_df),
            "test_metrics": {
                "mae": round(mae, 2),
                "rmse": round(rmse, 2),
                "mape_percent": round(mape, 2),
                "residual_std": round(self.residual_std, 2)
            },
            "baseline_comparisons": {
                "persistence_lag1": { "mae": round(mae_p1, 2), "rmse": round(rmse_p1, 2) },
                "seasonal_naive_lag24": { "mae": round(mae_p24, 2), "rmse": round(rmse_p24, 2) },
                "improvement_vs_naive_percent": round((1.0 - mae / mae_p24) * 100.0, 1)
            },
            "feature_importance": sorted_importance,
            "prediction_interval_std": round(self.residual_std, 2)
        }

        # Save model and metadata
        model_path = os.path.join(self.model_dir, "xgboost_price_model.json")
        meta_path = os.path.join(self.model_dir, "xgboost_metadata.json")
        self.model.save_model(model_path)
        with open(meta_path, "w") as f:
            json.dump(self.metadata, f, indent=2)

        return self.metadata

    def predict(self, df_raw: pd.DataFrame, horizon: int = 24) -> List[Dict[str, Any]]:
        """
        Generate forecast for the specified horizon with uncertainty bounds.
        Returns list of {timestamp, predicted_price, lower_bound_80, upper_bound_80, lower_bound_95, upper_bound_95}.
        """
        if self.model is None:
            model_path = os.path.join(self.model_dir, "xgboost_price_model.json")
            if not os.path.exists(model_path):
                for alt in ["../data/models/xgboost_price_model.json", "data/models/xgboost_price_model.json"]:
                    if os.path.exists(alt):
                        model_path = os.path.abspath(alt)
                        self.model_dir = os.path.dirname(model_path)
                        break
            if os.path.exists(model_path):
                self.model = xgb.XGBRegressor()
                self.model.load_model(model_path)
                meta_path = os.path.join(self.model_dir, "xgboost_metadata.json")
                if os.path.exists(meta_path):
                    with open(meta_path, "r") as f:
                        self.metadata = json.load(f)
                        self.residual_std = self.metadata.get("prediction_interval_std", 5.0)
            else:
                self.train(df_raw)

        df_feat = engineer_features(df_raw)
        latest_rows = df_feat.tail(horizon).copy()
        
        X = latest_rows[FEATURE_COLUMNS].ffill().fillna(0)
        preds = self.model.predict(X)

        results = []
        std = self.residual_std
        for i, (_, row) in enumerate(latest_rows.iterrows()):
            pred_val = float(preds[i])
            results.append({
                "timestamp": str(row['timestamp']),
                "predicted_price": round(pred_val, 2),
                "lower_bound_80": round(pred_val - 1.28 * std, 2),
                "upper_bound_80": round(pred_val + 1.28 * std, 2),
                "lower_bound_95": round(pred_val - 1.96 * std, 2),
                "upper_bound_95": round(pred_val + 1.96 * std, 2),
                "day_ahead_price": round(float(row.get('price_day_ahead', pred_val)), 2)
            })

        return results
