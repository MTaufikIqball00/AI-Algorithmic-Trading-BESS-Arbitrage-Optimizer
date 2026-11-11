"""
Rigorous Time-Series Evaluation Metrics for Solar Photovoltaic Forecasting.
Implements MAE, RMSE, non-zero safe MAPE, sMAPE, R-squared, and Prediction Interval Coverage Probability (PICP).
"""
import numpy as np
from typing import Dict, Any, Optional, Tuple


class ForecastEvaluator:
    """
    Computes standard regression and probabilistic metrics for solar generation models.
    """

    @staticmethod
    def evaluate(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        lower_interval_80: Optional[np.ndarray] = None,
        upper_interval_80: Optional[np.ndarray] = None,
        capacity_kw: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluate forecast metrics against ground truth.
        """
        y_t = np.asarray(y_true, dtype=np.float64)
        y_p = np.asarray(y_pred, dtype=np.float64)

        # Enforce physical non-negativity on predictions
        y_p = np.maximum(0.0, y_p)

        n = len(y_t)
        if n == 0:
            return {"error": "Zero samples evaluated"}

        residuals = y_t - y_p

        # 1. Mean Absolute Error (MAE)
        mae = float(np.mean(np.abs(residuals)))

        # 2. Root Mean Squared Error (RMSE)
        rmse = float(np.sqrt(np.mean(residuals ** 2)))

        # 3. Normalized MAE and RMSE (nMAE, nRMSE) if capacity is provided
        nmae = (mae / capacity_kw * 100.0) if capacity_kw and capacity_kw > 0 else None
        nrmse = (rmse / capacity_kw * 100.0) if capacity_kw and capacity_kw > 0 else None

        # 4. Non-zero safe MAPE:
        # Standard MAPE blows up towards infinity when y_true is near zero (nighttime/dawn/dusk).
        # We evaluate MAPE exclusively on daylight hours where y_true > 5% of capacity (or median)
        daylight_threshold = 0.05 * capacity_kw if (capacity_kw and capacity_kw > 0) else max(1.0, 0.05 * np.max(y_t))
        daylight_mask = y_t > daylight_threshold
        if np.any(daylight_mask):
            mape = float(np.mean(np.abs(residuals[daylight_mask] / y_t[daylight_mask])) * 100.0)
        else:
            mape = None

        # 5. Symmetric MAPE (sMAPE): bounded between 0% and 200%
        denominator = (np.abs(y_t) + np.abs(y_p)) / 2.0
        valid_denom = denominator > 1e-3
        if np.any(valid_denom):
            smape = float(np.mean(np.abs(residuals[valid_denom]) / denominator[valid_denom]) * 100.0)
        else:
            smape = 0.0

        # 6. Coefficient of Determination (R^2)
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((y_t - np.mean(y_t)) ** 2)
        r2 = float(1.0 - (ss_res / ss_tot)) if ss_tot > 1e-6 else 0.0

        # 7. Prediction Interval Coverage Probability (PICP) for 80% interval
        picp_80 = None
        if lower_interval_80 is not None and upper_interval_80 is not None:
            l = np.asarray(lower_interval_80, dtype=np.float64)
            u = np.asarray(upper_interval_80, dtype=np.float64)
            covered = (y_t >= l) & (y_t <= u)
            picp_80 = float(np.mean(covered) * 100.0)

        return {
            "sample_count": n,
            "mae": round(mae, 4),
            "rmse": round(rmse, 4),
            "nmae_pct": round(nmae, 2) if nmae is not None else None,
            "nrmse_pct": round(nrmse, 2) if nrmse is not None else None,
            "daylight_safe_mape_pct": round(mape, 2) if mape is not None else None,
            "smape_pct": round(smape, 2),
            "r2_score": round(r2, 4),
            "picp_80_pct": round(picp_80, 2) if picp_80 is not None else None,
            "residual_mean": round(float(np.mean(residuals)), 4),
            "residual_std": round(float(np.std(residuals)), 4)
        }
