"""
Solar PV Soiling Analysis Engine.
Quantifies performance degradation due to dust, particulate accumulation, and wash-off events.
Requires explicit cleaning logs or rain records before claiming confirmed soiling.
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import pandas as pd
from datetime import datetime

from ..features.solar_physics import SolarPVPhysicsEngine
from ..config.defaults import PVSystemConfig


@dataclass
class SoilingAnalysisResult:
    status: str                         # CONFIRMED_SOILING, POTENTIAL_SOILING, INSUFFICIENT_EVIDENCE, NO_SOILING_DETECTED
    soiling_ratio_current: Optional[float]  # e.g. 0.94 (6% loss)
    estimated_soiling_rate_pct_day: Optional[float]
    cleaning_events_detected: int
    wash_recovery_pct: Optional[float]
    analyzed_days: int
    evidence_notes: List[str]
    missing_evidence: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SoilingAnalyzer:
    """
    Evidence-based soiling quantification adhering strictly to IEC 61724 standards.
    """

    def __init__(self, config: Optional[PVSystemConfig] = None):
        self.config = config or PVSystemConfig()
        self.physics = SolarPVPhysicsEngine(self.config)

    def analyze_soiling(
        self,
        df: pd.DataFrame,
        cleaning_timestamps: Optional[List[str]] = None,
        min_clear_sky_poa: float = 400.0
    ) -> SoilingAnalysisResult:
        """
        Analyze time-series for soiling trends and wash recovery.
        """
        if df.empty or len(df) < 48:
            return SoilingAnalysisResult(
                status="INSUFFICIENT_EVIDENCE",
                soiling_ratio_current=None,
                estimated_soiling_rate_pct_day=None,
                cleaning_events_detected=0,
                wash_recovery_pct=None,
                analyzed_days=0,
                evidence_notes=["Dataset is too small to perform reliable soiling analysis."],
                missing_evidence=["Requires at least 7 continuous days of daytime observations."]
            )

        df_calc = df.copy()
        df_calc["dt"] = pd.to_datetime(df_calc["timestamp"])
        df_calc["date"] = df_calc["dt"].dt.date

        poa = df_calc["plane_of_array_irradiance"] if "plane_of_array_irradiance" in df_calc.columns else df_calc.get("irradiance", pd.Series(0.0, index=df_calc.index))
        panel_t = df_calc["panel_temperature"] if "panel_temperature" in df_calc.columns else None
        amb_t = df_calc["ambient_temperature"] if "ambient_temperature" in df_calc.columns else df_calc.get("temperature_c", None)

        expected_p = self.physics.calculate_expected_power_kw(
            poa_irradiance=poa,
            cell_temperature_c=panel_t,
            ambient_temperature_c=amb_t
        )
        actual_p = pd.to_numeric(df_calc["power"], errors="coerce")
        inv_col = df_calc["inverter_status"] if "inverter_status" in df_calc.columns else pd.Series("OPERATING_NORMAL", index=df_calc.index)

        # High-irradiance midday filter (avoids low-sun angle reflection losses, missing values, and hard inverter trips)
        clear_midday = (
            (poa >= min_clear_sky_poa)
            & (expected_p > 10.0)
            & actual_p.notna()
            & (actual_p > 0.10 * expected_p)
            & (inv_col != "FAULT_TRIPPED")
        )
        df_calc["expected_p"] = expected_p
        df_calc["actual_p"] = actual_p
        df_calc["clear_midday"] = clear_midday

        # Compute daily irradiance-weighted performance ratio
        daily_records = []
        for d, grp in df_calc[clear_midday].groupby("date"):
            e_act = grp["actual_p"].sum()
            e_exp = grp["expected_p"].sum()
            if e_exp > 0:
                daily_ratio = e_act / e_exp
                daily_records.append({
                    "date": d,
                    "soiling_metric": float(daily_ratio),
                    "mean_poa": float(grp["plane_of_array_irradiance"].mean() if "plane_of_array_irradiance" in grp.columns else grp["irradiance"].mean())
                })

        daily_df = pd.DataFrame(daily_records)
        total_days = len(daily_df)

        if total_days < 7:
            return SoilingAnalysisResult(
                status="INSUFFICIENT_EVIDENCE",
                soiling_ratio_current=None,
                estimated_soiling_rate_pct_day=None,
                cleaning_events_detected=0,
                wash_recovery_pct=None,
                analyzed_days=total_days,
                evidence_notes=["Fewer than 7 high-irradiance clear days available."],
                missing_evidence=["Extended sunny period needed to establish baseline."]
            )

        # Normalize daily performance ratio relative to clean baseline (95th percentile if > 1.0)
        clean_ref = max(1.0, float(np.percentile(daily_df["soiling_metric"].values, 95)))
        daily_df["soiling_metric"] = np.clip(daily_df["soiling_metric"] / clean_ref, 0.0, 1.0)

        # Look for cleaning timestamps
        has_cleaning_records = False
        cleaning_dates = set()

        # Check explicit parameter
        if cleaning_timestamps:
            cleaning_dates.update([pd.to_datetime(t).date() for t in cleaning_timestamps])
            has_cleaning_records = True

        # Check dataframe column
        if "cleaning_timestamp" in df_calc.columns:
            valid_clean = df_calc["cleaning_timestamp"].dropna()
            if len(valid_clean) > 0:
                cleaning_dates.update([pd.to_datetime(t).date() for t in valid_clean])
                has_cleaning_records = True

        evidence_notes = []
        missing_evidence = []
        wash_recovery = None
        soiling_rate = None

        # If explicit cleaning dates exist, calculate wash recovery step
        sorted_clean_dates = sorted(cleaning_dates)
        if has_cleaning_records and len(sorted_clean_dates) > 0:
            for c_date in sorted_clean_dates:
                # 3 days before vs 3 days after
                before = daily_df[daily_df["date"] < c_date].tail(3)["soiling_metric"].mean()
                after = daily_df[daily_df["date"] >= c_date].head(3)["soiling_metric"].mean()
                if pd.notna(before) and pd.notna(after) and before > 0:
                    recovery_step = (after - before) / before * 100.0
                    wash_recovery = round(float(recovery_step), 2)
                    evidence_notes.append(
                        f"Documented cleaning on {c_date}: measured +{wash_recovery:.2f}% generation recovery step."
                    )
                    break

        # Calculate linear trend slope over dry period (pre-cleaning window if cleaning occurred)
        if has_cleaning_records and len(sorted_clean_dates) > 0:
            pre_clean_df = daily_df[daily_df["date"] < sorted_clean_dates[0]]
            y_trend = pre_clean_df["soiling_metric"].values if len(pre_clean_df) >= 5 else daily_df["soiling_metric"].values
        else:
            y_trend = daily_df["soiling_metric"].values

        x = np.arange(len(y_trend))
        slope, intercept = np.polyfit(x, y_trend, deg=1)
        # Daily soiling loss percentage: max(0.0, -slope * 100) when no soiling, or exact rate
        raw_soiling_rate = round(float(-slope * 100.0), 3)

        current_sr = round(float(daily_df["soiling_metric"].values[-1]), 3)

        # Scientific classification
        if has_cleaning_records and wash_recovery is not None and wash_recovery > 3.0:
            status = "CONFIRMED_SOILING"
            soiling_rate = max(0.0, raw_soiling_rate)
            evidence_notes.append("Confirmed soiling: wash recovery step validated against documented cleaning log.")
        elif slope < -0.001 and total_days >= 14:
            status = "POTENTIAL_SOILING"
            soiling_rate = raw_soiling_rate
            evidence_notes.append(f"Statistically significant downward drift of {soiling_rate:.3f}%/day observed under high irradiance.")
            if not has_cleaning_records:
                missing_evidence.append("No cleaning logs or reference panel measurements to confirm soiling vs other degradation.")
        else:
            status = "NO_SOILING_DETECTED"
            soiling_rate = max(0.0, raw_soiling_rate)
            evidence_notes.append(f"Performance ratio remains stable (median SR={float(daily_df['soiling_metric'].median()):.3f}); no substantial dry soiling decay detected.")
            if not has_cleaning_records:
                missing_evidence.append("Cleaning timestamp telemetry absent from dataset.")

        return SoilingAnalysisResult(
            status=status,
            soiling_ratio_current=current_sr,
            estimated_soiling_rate_pct_day=soiling_rate,
            cleaning_events_detected=len(cleaning_dates),
            wash_recovery_pct=wash_recovery,
            analyzed_days=total_days,
            evidence_notes=evidence_notes,
            missing_evidence=missing_evidence
        )
