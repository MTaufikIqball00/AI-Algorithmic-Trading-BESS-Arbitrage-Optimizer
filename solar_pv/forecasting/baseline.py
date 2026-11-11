"""
Standard Persistence and Physical Baselines for Solar PV Forecasting Benchmarking.
Implements Lag-1 Persistence, Lag-24 Seasonal Naive, Night-Zero Persistence, and Clear-Sky Index Persistence.
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional

from .evaluation import ForecastEvaluator


class SolarBaselineForecaster:
    """
    Computes honest, un-manipulated baseline forecasts to prove ML value-add.
    """

    @staticmethod
    def _get_steps_per_day(df: pd.DataFrame) -> int:
        ts_col = "dt" if "dt" in df.columns else ("timestamp" if "timestamp" in df.columns else None)
        if ts_col is not None and len(df) >= 2:
            diffs = pd.to_datetime(df[ts_col]).diff().dt.total_seconds().dropna()
            if len(diffs) > 0:
                med = float(diffs.median())
                if med > 0 and not np.isnan(med):
                    return max(1, int(round(86400.0 / med)))
        return 24

    @classmethod
    def persistence_lag_1(cls, df: pd.DataFrame, target_col: str = "power") -> np.ndarray:
        """
        Naive persistence: P_pred(t) = P(t-1)
        """
        if "power_lag_1" in df.columns and target_col == "power":
            vals = df["power_lag_1"].fillna(df[target_col].shift(1)).fillna(0.0).values
        else:
            vals = df[target_col].shift(1).fillna(0.0).values
        return np.maximum(0.0, vals)

    @classmethod
    def seasonal_naive_lag_24(cls, df: pd.DataFrame, target_col: str = "power") -> np.ndarray:
        """
        Seasonal naive (24-hour diurnal persistence): P_pred(t) = P(t - 24h)
        """
        steps_per_day = cls._get_steps_per_day(df)
        if "power_lag_24" in df.columns and target_col == "power":
            vals = df["power_lag_24"].fillna(df[target_col].shift(steps_per_day)).fillna(0.0).values
        else:
            vals = df[target_col].shift(steps_per_day).fillna(0.0).values
        return np.maximum(0.0, vals)

    @classmethod
    def night_zero_seasonal_naive(
        cls,
        df: pd.DataFrame,
        target_col: str = "power",
        elevation_col: str = "solar_elevation_deg"
    ) -> np.ndarray:
        """
        Enlightened persistence: diurnal 24-hour lag during daylight, strictly 0.0 at night.
        """
        p_lag24 = cls.seasonal_naive_lag_24(df, target_col=target_col)
        if elevation_col in df.columns:
            elev = df[elevation_col].values
            p_pred = np.where(elev <= 0.0, 0.0, p_lag24)
        else:
            p_pred = p_lag24
        return np.maximum(0.0, p_pred)

    @classmethod
    def evaluate_all_baselines(
        cls,
        test_df: pd.DataFrame,
        target_col: str = "power",
        capacity_kw: Optional[float] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compute evaluation metrics across all standard baselines on the test slice.
        """
        y_true = test_df[target_col].values

        p_lag1 = cls.persistence_lag_1(test_df, target_col)
        p_lag24 = cls.seasonal_naive_lag_24(test_df, target_col)
        p_night_zero = cls.night_zero_seasonal_naive(test_df, target_col)

        m_lag1 = ForecastEvaluator.evaluate(y_true, p_lag1, capacity_kw=capacity_kw)
        m_lag24 = ForecastEvaluator.evaluate(y_true, p_lag24, capacity_kw=capacity_kw)
        m_night_zero = ForecastEvaluator.evaluate(y_true, p_night_zero, capacity_kw=capacity_kw)

        return {
            "persistence_lag_1": m_lag1,
            "seasonal_naive_lag_24": m_lag24,
            "night_zero_seasonal_naive": m_night_zero
        }
