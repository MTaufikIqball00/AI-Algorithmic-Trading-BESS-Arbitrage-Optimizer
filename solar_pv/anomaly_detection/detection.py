"""
Statistical and Machine Learning Anomaly Detection for Solar PV.
Computes physical residuals, Robust Z-scores via Median Absolute Deviation (MAD),
and multivariate Isolation Forest anomaly scores.
Excludes natural nighttime zero generation from anomaly alerts.
"""
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional, List
from sklearn.ensemble import IsolationForest

from ..features.solar_physics import SolarPVPhysicsEngine
from ..config.defaults import PVSystemConfig


class PVAnomalyDetector:
    """
    Identifies statistical and physical anomalies in solar PV generation time-series.
    """

    def __init__(
        self,
        config: Optional[PVSystemConfig] = None,
        z_threshold: float = 3.0,
        isolation_forest_contamination: float = 0.03,
        min_daylight_irradiance: float = 20.0
    ):
        self.config = config or PVSystemConfig()
        self.physics = SolarPVPhysicsEngine(self.config)
        self.z_threshold = z_threshold
        self.isolation_forest_contamination = isolation_forest_contamination
        self.min_daylight_irradiance = min_daylight_irradiance
        self.iso_forest: Optional[IsolationForest] = None

    def compute_residuals(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute expected physical generation and residual:
        Residual R = P_actual - P_expected
        """
        df_out = df.copy()
        poa = df_out["plane_of_array_irradiance"] if "plane_of_array_irradiance" in df_out.columns else df_out.get("irradiance", pd.Series(0.0, index=df_out.index))
        panel_t = df_out["panel_temperature"] if "panel_temperature" in df_out.columns else None
        amb_t = df_out["ambient_temperature"] if "ambient_temperature" in df_out.columns else df_out.get("temperature_c", None)
        wind_s = df_out.get("wind_speed", None)

        expected_p = self.physics.calculate_expected_power_kw(
            poa_irradiance=poa,
            cell_temperature_c=panel_t,
            ambient_temperature_c=amb_t,
            wind_speed_m_s=wind_s
        )

        actual_p = df_out["power"].fillna(0.0) if "power" in df_out.columns else df_out.get("solar_gen_mw", pd.Series(0.0, index=df_out.index)) * 1000.0

        # Daylight mask: only evaluate when sun is physically active
        daylight_mask = poa > self.min_daylight_irradiance

        df_out["expected_power_kw"] = np.round(expected_p, 2)
        df_out["residual_kw"] = np.where(daylight_mask, np.round(actual_p - expected_p, 2), 0.0)
        df_out["residual_ratio"] = np.where(daylight_mask & (expected_p > 1.0), actual_p / expected_p, 1.0)
        df_out["is_daylight"] = daylight_mask

        return df_out

    def detect_robust_zscore(self, df_with_residuals: pd.DataFrame) -> pd.Series:
        """
        Detect outliers using Median Absolute Deviation (MAD) robust Z-score:
        Z = (Residual - Median) / (MAD * 1.4826)
        """
        daylight = df_with_residuals["is_daylight"]
        res = df_with_residuals.loc[daylight, "residual_kw"]

        if len(res) < 10:
            return pd.Series(False, index=df_with_residuals.index)

        med = res.median()
        mad = (res - med).abs().median()
        scale = mad * 1.4826 if mad > 1e-4 else res.std()

        if scale < 1e-4:
            scale = 1.0

        z_scores = pd.Series(0.0, index=df_with_residuals.index)
        z_scores.loc[daylight] = (res - med) / scale

        # Anomaly is flagged when residual is significantly negative (underperformance)
        is_anomaly = (z_scores < -self.z_threshold) & daylight
        return is_anomaly

    def fit_predict_isolation_forest(self, df_with_residuals: pd.DataFrame) -> pd.Series:
        """
        Unsupervised multivariate anomaly detection via Isolation Forest.
        Features: [actual_power, irradiance, residual, panel_temperature]
        """
        daylight = df_with_residuals["is_daylight"]
        daylight_indices = df_with_residuals.index[daylight]

        if len(daylight_indices) < 30:
            return pd.Series(False, index=df_with_residuals.index)

        feature_cols = ["power", "expected_power_kw", "residual_kw"]
        if "plane_of_array_irradiance" in df_with_residuals.columns:
            feature_cols.append("plane_of_array_irradiance")
        if "panel_temperature" in df_with_residuals.columns:
            feature_cols.append("panel_temperature")

        X = df_with_residuals.loc[daylight, feature_cols].fillna(0.0)

        self.iso_forest = IsolationForest(
            contamination=self.isolation_forest_contamination,
            random_state=42,
            n_estimators=100
        )
        preds = self.iso_forest.fit_predict(X)
        # -1 indicates anomaly, 1 indicates inlier
        anomaly_series = pd.Series(False, index=df_with_residuals.index)
        anomaly_series.loc[daylight] = (preds == -1)
        return anomaly_series

    def detect_physical_derate(self, df_with_residuals: pd.DataFrame) -> pd.Series:
        """
        Detect direct physical underperformance where actual output falls significantly below
        first-principles expected power (< 70% of expected) under meaningful daylight capacity.
        """
        daylight = df_with_residuals["is_daylight"]
        min_exp = max(1.0, 0.15 * self.config.rated_dc_power_kw)
        is_derate = (
            daylight
            & (df_with_residuals["expected_power_kw"] >= min_exp)
            & (df_with_residuals["residual_ratio"] < 0.70)
        )
        return is_derate

    def detect_stuck_sensor(self, df_with_residuals: pd.DataFrame) -> pd.Series:
        """
        Detect frozen/flatlined telemetry (zero variance over >= 6 steps while irradiance varies).
        """
        if len(df_with_residuals) < 6:
            return pd.Series(False, index=df_with_residuals.index)

        daylight = df_with_residuals["is_daylight"]
        poa_col = "plane_of_array_irradiance" if "plane_of_array_irradiance" in df_with_residuals.columns else "irradiance"
        if poa_col not in df_with_residuals.columns:
            return pd.Series(False, index=df_with_residuals.index)

        poa_std = df_with_residuals[poa_col].rolling(6, min_periods=6).std().fillna(0.0)
        p_std = df_with_residuals["power"].rolling(6, min_periods=6).std().fillna(1.0)
        stuck_power = daylight & (df_with_residuals["power"] > 0.1) & (p_std < 1e-5) & (poa_std > 5.0)

        if "panel_temperature" in df_with_residuals.columns:
            t_std = df_with_residuals["panel_temperature"].rolling(6, min_periods=6).std().fillna(1.0)
            stuck_temp = daylight & (t_std < 1e-5) & (poa_std > 10.0)
            return stuck_power | stuck_temp

        return stuck_power
