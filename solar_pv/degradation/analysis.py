"""
Long-Term Photovoltaic Degradation Analysis Engine.
Estimates annual PV cell degradation rates with strict data sufficiency enforcement,
irradiance normalization, temperature adjustment, and 95% confidence intervals.
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import pandas as pd

from .trend import RobustTrendEstimator
from ..features.solar_physics import SolarPVPhysicsEngine
from ..config.defaults import PVSystemConfig


@dataclass
class DegradationAnalysisResult:
    status: str                                  # SUFFICIENT_DATA_VALIDATED or INSUFFICIENT_DATA_DURATION
    annualized_degradation_pct_year: Optional[float]
    confidence_interval_95: Optional[Tuple[float, float]]
    data_duration_days: float
    is_statistically_defensible: bool
    normalization_method: str
    sample_points_analyzed: int
    scientific_warning: Optional[str]
    evidence_notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DegradationAnalyzer:
    """
    Evaluates historical photovoltaic degradation adhering to NREL / Sandia analytical guidelines.
    """

    MIN_REQUIRED_DAYS_FOR_ANNUALIZED_RATE = 365.0 # Minimum 1 full year to eliminate seasonality bias

    def __init__(self, config: Optional[PVSystemConfig] = None):
        self.config = config or PVSystemConfig()
        self.physics = SolarPVPhysicsEngine(self.config)

    def analyze_degradation(
        self,
        df: pd.DataFrame,
        target_col: str = "power"
    ) -> DegradationAnalysisResult:
        """
        Analyze multi-year or long-term PV time-series for annualized capacity degradation.
        """
        if df.empty or len(df) < 50:
            return DegradationAnalysisResult(
                status="INSUFFICIENT_DATA_DURATION",
                annualized_degradation_pct_year=None,
                confidence_interval_95=None,
                data_duration_days=0.0,
                is_statistically_defensible=False,
                normalization_method="N/A",
                sample_points_analyzed=0,
                scientific_warning="Dataset contains insufficient observations for degradation analysis.",
                evidence_notes=["Minimum 365 days required."]
            )

        df_calc = df.copy()
        df_calc["dt"] = pd.to_datetime(df_calc["timestamp"])
        df_calc = df_calc.sort_values("dt").reset_index(drop=True)

        start_dt = df_calc["dt"].iloc[0]
        end_dt = df_calc["dt"].iloc[-1]
        duration_days = (end_dt - start_dt).total_seconds() / 86400.0

        evidence_notes = [
            f"Dataset spans {start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')} ({duration_days:.1f} days)."
        ]

        # 1. Scientific Data Sufficiency Gate:
        # If duration < 365 days, do NOT calculate or publish an annualized degradation rate
        if duration_days < self.MIN_REQUIRED_DAYS_FOR_ANNUALIZED_RATE:
            warning_msg = (
                f"Data duration ({duration_days:.1f} days) is less than the required minimum 365.0 days. "
                "Calculating an annualized degradation rate on short data conflates seasonal solar zenith/temperature variations "
                "with true semiconductor degradation. Under the core scientific principles, annualized degradation rate is withheld."
            )
            evidence_notes.append("Scientific sufficiency check failed: < 365 days coverage.")
            return DegradationAnalysisResult(
                status="INSUFFICIENT_DATA_DURATION",
                annualized_degradation_pct_year=None,
                confidence_interval_95=None,
                data_duration_days=round(duration_days, 1),
                is_statistically_defensible=False,
                normalization_method="IEC 61724 Temperature-Corrected Performance Index",
                sample_points_analyzed=len(df_calc),
                scientific_warning=warning_msg,
                evidence_notes=evidence_notes
            )

        # 2. Temperature and Irradiance Normalization
        poa = df_calc["plane_of_array_irradiance"] if "plane_of_array_irradiance" in df_calc.columns else df_calc.get("irradiance", pd.Series(0.0, index=df_calc.index))
        panel_t = df_calc.get("panel_temperature", None)
        amb_t = df_calc.get("ambient_temperature", None)

        expected_p = self.physics.calculate_expected_power_kw(
            poa_irradiance=poa,
            cell_temperature_c=panel_t,
            ambient_temperature_c=amb_t
        )
        actual_p = df_calc[target_col].fillna(0.0)

        # Midday clear-sky filter: POA > 400 W/m^2, expected_p > 10 kW
        valid_mask = (poa > 400.0) & (expected_p > 10.0) & (actual_p > 1.0)
        df_valid = df_calc[valid_mask].copy()

        if len(df_valid) < 100:
            return DegradationAnalysisResult(
                status="INSUFFICIENT_DATA_DURATION",
                annualized_degradation_pct_year=None,
                confidence_interval_95=None,
                data_duration_days=round(duration_days, 1),
                is_statistically_defensible=False,
                normalization_method="IEC 61724 Midday Performance Index",
                sample_points_analyzed=len(df_valid),
                scientific_warning="Fewer than 100 valid midday points after weather filtering.",
                evidence_notes=evidence_notes
            )

        # Daily performance metric aggregation to eliminate intra-day variance
        df_valid["date"] = df_valid["dt"].dt.date
        df_valid["norm_ratio"] = df_valid[target_col] / expected_p[valid_mask]

        daily_series = df_valid.groupby("date")["norm_ratio"].median().dropna()

        # 3. Robust Theil-Sen Trend Estimation
        dates_utc = pd.to_datetime(daily_series.index, utc=True)
        start_utc = pd.to_datetime(start_dt, utc=True)
        dates_numeric = (dates_utc - start_utc).total_seconds() / (86400.0 * 365.25) # in years
        y_vals = daily_series.values

        slope_year, intercept, low_ci, high_ci = RobustTrendEstimator.theil_sen_slope(
            dates_numeric.values, y_vals
        )

        # Degradation rate (%/year) = -slope_year * 100
        deg_rate_pct = round(float(-slope_year * 100.0), 2)
        ci_low_pct = round(float(-high_ci * 100.0), 2)
        ci_high_pct = round(float(-low_ci * 100.0), 2)

        evidence_notes.append(f"Analyzed {len(daily_series)} daily midday normalized performance indices.")
        evidence_notes.append(f"Estimated annual degradation rate: {deg_rate_pct}%/year (95% CI: [{ci_low_pct}%, {ci_high_pct}%]).")

        return DegradationAnalysisResult(
            status="SUFFICIENT_DATA_VALIDATED",
            annualized_degradation_pct_year=deg_rate_pct,
            confidence_interval_95=(ci_low_pct, ci_high_pct),
            data_duration_days=round(duration_days, 1),
            is_statistically_defensible=True,
            normalization_method="IEC 61724 Daily Midday Performance Index with Theil-Sen Estimator",
            sample_points_analyzed=len(daily_series),
            scientific_warning=None,
            evidence_notes=evidence_notes
        )
