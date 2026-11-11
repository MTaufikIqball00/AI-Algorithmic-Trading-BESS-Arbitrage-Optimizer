"""
Multi-Criteria Evidence-Based Anomaly Classifier for Solar PV Systems.
Strictly maps anomalous observations to physical root causes based on deterministic evidence:
- WEATHER_RELATED
- POTENTIAL_SOILING
- POTENTIAL_EQUIPMENT_FAULT
- SENSOR_FAULT
- UNKNOWN_NEEDS_INVESTIGATION
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Any, Optional, Tuple

from .evidence import (
    AnomalyClassification,
    AnomalySeverity,
    EvidenceBundle,
    AnomalyEvent
)
from ..config.defaults import PVSystemConfig
from .detection import PVAnomalyDetector


class PVAnomalyClassifier:
    """
    Classifies detected anomalies according to rigorous evidence-based taxonomy.
    """

    def __init__(self, config: Optional[PVSystemConfig] = None):
        self.config = config or PVSystemConfig()
        self.detector = PVAnomalyDetector(self.config)

    def classify_dataset(
        self,
        df_raw: pd.DataFrame,
        asset_id: str = "pv_array_01"
    ) -> Tuple[List[AnomalyEvent], pd.DataFrame]:
        """
        Run detection and evidence-based classification across time-series DataFrame.
        Returns:
            (anomaly_events, df_with_diagnostics)
        """
        df_res = self.detector.compute_residuals(df_raw)
        is_z_anomaly = self.detector.detect_robust_zscore(df_res)
        is_iso_anomaly = self.detector.fit_predict_isolation_forest(df_res)
        is_phys_derate = self.detector.detect_physical_derate(df_res)
        is_stuck_telemetry = self.detector.detect_stuck_sensor(df_res)

        sens_col = df_res["sensor_status"] if "sensor_status" in df_res.columns else pd.Series("NORMAL", index=df_res.index)
        inv_col = df_res["inverter_status"] if "inverter_status" in df_res.columns else pd.Series("NORMAL", index=df_res.index)
        is_telemetry_anomaly = sens_col.isin(["STUCK", "DISCONNECTED", "OUT_OF_BOUNDS"]) | inv_col.isin(["FAULT_TRIPPED"]) | is_stuck_telemetry

        # Statistical/ML anomalies must correspond to a genuine performance deficit (< 80% of expected)
        # under meaningful daylight capacity (>= 15% of rated DC) so low-angle dawn/dusk or minor fluctuations are not flagged.
        min_meaningful_exp = max(1.0, 0.15 * self.config.rated_dc_power_kw)
        has_power_deficit = (df_res["residual_ratio"] < 0.80) & (df_res["expected_power_kw"] >= min_meaningful_exp)
        is_perf_anomaly = (is_z_anomaly | is_iso_anomaly | is_phys_derate) & has_power_deficit

        df_res["is_anomaly"] = (is_perf_anomaly | is_telemetry_anomaly) & df_res["is_daylight"]

        events: List[AnomalyEvent] = []

        # Find continuous anomalous segments
        anomaly_indices = df_res.index[df_res["is_anomaly"]].tolist()
        if not anomaly_indices:
            return [], df_res

        # Group consecutive indices into events
        grouped_events = []
        current_group = [anomaly_indices[0]]

        for idx in anomaly_indices[1:]:
            if idx == current_group[-1] + 1:
                current_group.append(idx)
            else:
                grouped_events.append(current_group)
                current_group = [idx]
        grouped_events.append(current_group)

        # Classify each event
        for group in grouped_events:
            event = self._classify_event_group(df_res.loc[group], asset_id)
            if event is not None:
                events.append(event)

        return events, df_res

    def _classify_event_group(
        self,
        group_df: pd.DataFrame,
        asset_id: str
    ) -> Optional[AnomalyEvent]:
        """
        Synthesize evidence bundle and classify root cause for an event group.
        """
        start_t = str(group_df["timestamp"].iloc[0])
        end_t = str(group_df["timestamp"].iloc[-1])

        mean_actual = float(group_df["power"].mean())
        mean_expected = float(group_df["expected_power_kw"].mean())
        mean_residual = float(group_df["residual_kw"].mean())
        mean_poa = float(group_df["plane_of_array_irradiance"].mean()) if "plane_of_array_irradiance" in group_df.columns else float(group_df.get("irradiance", pd.Series(0.0)).mean())
        cloud_cov = float(group_df["cloud_cover"].mean()) if "cloud_cover" in group_df.columns else 0.0

        v_dc = float(group_df["voltage"].mean()) if "voltage" in group_df.columns and group_df["voltage"].notna().any() else None
        i_dc = float(group_df["current"].mean()) if "current" in group_df.columns and group_df["current"].notna().any() else None

        inv_status = str(group_df["inverter_status"].iloc[0]) if "inverter_status" in group_df.columns else "UNKNOWN"
        sens_status = str(group_df["sensor_status"].iloc[0]) if "sensor_status" in group_df.columns else "UNKNOWN"

        ratio = (mean_actual / mean_expected) if mean_expected > 1.0 else 1.0
        evidence_notes: List[str] = []

        # 1. Rule: Sensor Fault
        # Stuck sensor (zero variance over >= 6 observations) or explicit sensor error flag
        is_stuck = False
        if len(group_df) >= 6:
            p_var = float(group_df["power"].var())
            if p_var < 1e-6 and mean_actual > 0:
                is_stuck = True
                evidence_notes.append("Power telemetry flatlined with zero variance during changing irradiance.")
        
        if sens_status in ["STUCK", "DISCONNECTED", "OUT_OF_BOUNDS"] or is_stuck:
            classification = AnomalyClassification.SENSOR_FAULT
            severity = AnomalySeverity.MEDIUM
            confidence = 0.95
            evidence_notes.append(f"Sensor diagnostic status: {sens_status}.")
            bundle = EvidenceBundle(
                irradiance_normalized_ratio=round(ratio, 3),
                is_weather_explained=False,
                cloud_cover=round(cloud_cov, 2),
                irradiance_w_per_m2=round(mean_poa, 1),
                voltage_v=round(v_dc, 1) if v_dc is not None else None,
                current_a=round(i_dc, 2) if i_dc is not None else None,
                inverter_status=inv_status,
                sensor_status=sens_status,
                days_since_cleaning=None,
                cumulative_rain_mm=None,
                is_stuck_sensor=is_stuck,
                evidence_notes=evidence_notes
            )
            return AnomalyEvent(
                asset_id=asset_id,
                start_time=start_t,
                end_time=end_t,
                actual_power_kw=round(mean_actual, 2),
                expected_power_kw=round(mean_expected, 2),
                residual_kw=round(mean_residual, 2),
                classification=classification,
                severity=severity,
                confidence=confidence,
                evidence=bundle,
                model_version="solar_anomaly_v1.0",
                data_quality="SUSPECT_SENSOR"
            )

        # 2. Rule: Potential Equipment Fault
        # Inverter trip / electrical disconnect / current collapse during high irradiance
        if inv_status == "FAULT_TRIPPED" or (mean_poa > 400.0 and mean_actual < 0.05 * self.config.rated_dc_power_kw):
            classification = AnomalyClassification.POTENTIAL_EQUIPMENT_FAULT
            severity = AnomalySeverity.CRITICAL if mean_actual <= 0.01 else AnomalySeverity.HIGH
            confidence = 0.92
            evidence_notes.append(f"Inverter status '{inv_status}' or severe power collapse ({mean_actual:.1f} kW) under high irradiance ({mean_poa:.1f} W/m^2).")
            if v_dc is not None and v_dc > 200.0 and (i_dc is not None and i_dc < 0.1):
                evidence_notes.append(f"DC open circuit voltage present ({v_dc:.1f} V) with zero current ({i_dc:.2f} A) indicates inverter breaker open or contactor trip.")
            bundle = EvidenceBundle(
                irradiance_normalized_ratio=round(ratio, 3),
                is_weather_explained=False,
                cloud_cover=round(cloud_cov, 2),
                irradiance_w_per_m2=round(mean_poa, 1),
                voltage_v=round(v_dc, 1) if v_dc is not None else None,
                current_a=round(i_dc, 2) if i_dc is not None else None,
                inverter_status=inv_status,
                sensor_status=sens_status,
                days_since_cleaning=None,
                cumulative_rain_mm=None,
                is_stuck_sensor=False,
                evidence_notes=evidence_notes
            )
            return AnomalyEvent(
                asset_id=asset_id,
                start_time=start_t,
                end_time=end_t,
                actual_power_kw=round(mean_actual, 2),
                expected_power_kw=round(mean_expected, 2),
                residual_kw=round(mean_residual, 2),
                classification=classification,
                severity=severity,
                confidence=confidence,
                evidence=bundle,
                model_version="solar_anomaly_v1.0",
                data_quality="HARDWARE_ANOMALY"
            )

        # 3. Rule: Weather-Related Reduction
        # High cloud cover or low irradiance explain the lower output
        if cloud_cov > 0.65 or mean_poa < 250.0:
            classification = AnomalyClassification.WEATHER_RELATED
            severity = AnomalySeverity.LOW
            confidence = 0.88
            if cloud_cov > 0.65:
                evidence_notes.append(f"Production drop corresponds with heavy cloud cover ({cloud_cov*100:.1f}%) and attenuated irradiance ({mean_poa:.1f} W/m^2).")
            else:
                evidence_notes.append(f"Production variance under low-irradiance / cloud-transient conditions ({mean_poa:.1f} W/m^2); spatial cloud shading or diffuse sky attenuation.")
            bundle = EvidenceBundle(
                irradiance_normalized_ratio=round(ratio, 3),
                is_weather_explained=True,
                cloud_cover=round(cloud_cov, 2),
                irradiance_w_per_m2=round(mean_poa, 1),
                voltage_v=round(v_dc, 1) if v_dc is not None else None,
                current_a=round(i_dc, 2) if i_dc is not None else None,
                inverter_status=inv_status,
                sensor_status=sens_status,
                days_since_cleaning=None,
                cumulative_rain_mm=None,
                is_stuck_sensor=False,
                evidence_notes=evidence_notes
            )
            return AnomalyEvent(
                asset_id=asset_id,
                start_time=start_t,
                end_time=end_t,
                actual_power_kw=round(mean_actual, 2),
                expected_power_kw=round(mean_expected, 2),
                residual_kw=round(mean_residual, 2),
                classification=classification,
                severity=severity,
                confidence=confidence,
                evidence=bundle,
                model_version="solar_anomaly_v1.0",
                data_quality="VALID_WEATHER_EFFECT"
            )

        # 4. Rule: Potential Soiling
        # Requires sustained multi-interval loss (at least 4 consecutive daylight steps), high irradiance, and clear sky
        if len(group_df) >= 4 and mean_poa >= 450.0 and 0.60 <= ratio <= 0.88 and cloud_cov <= 0.30:
            classification = AnomalyClassification.POTENTIAL_SOILING
            severity = AnomalySeverity.MEDIUM
            confidence = 0.78
            evidence_notes.append(f"Clear sky ({cloud_cov*100:.0f}% clouds) with sustained irradiance-normalized underperformance (ratio {ratio:.2f}).")
            bundle = EvidenceBundle(
                irradiance_normalized_ratio=round(ratio, 3),
                is_weather_explained=False,
                cloud_cover=round(cloud_cov, 2),
                irradiance_w_per_m2=round(mean_poa, 1),
                voltage_v=round(v_dc, 1) if v_dc is not None else None,
                current_a=round(i_dc, 2) if i_dc is not None else None,
                inverter_status=inv_status,
                sensor_status=sens_status,
                days_since_cleaning=None,
                cumulative_rain_mm=None,
                is_stuck_sensor=False,
                evidence_notes=evidence_notes
            )
            return AnomalyEvent(
                asset_id=asset_id,
                start_time=start_t,
                end_time=end_t,
                actual_power_kw=round(mean_actual, 2),
                expected_power_kw=round(mean_expected, 2),
                residual_kw=round(mean_residual, 2),
                classification=classification,
                severity=severity,
                confidence=confidence,
                evidence=bundle,
                model_version="solar_anomaly_v1.0",
                data_quality="POTENTIAL_SOILING"
            )

        # 5. Default Fallback: Unknown / Needs Investigation
        # Insufficient or conflicting evidence
        evidence_notes.append("Inconclusive physical evidence: power reduction cannot be definitively attributed to weather, soiling, or hardware.")
        bundle = EvidenceBundle(
            irradiance_normalized_ratio=round(ratio, 3),
            is_weather_explained=False,
            cloud_cover=round(cloud_cov, 2),
            irradiance_w_per_m2=round(mean_poa, 1),
            voltage_v=round(v_dc, 1) if v_dc is not None else None,
            current_a=round(i_dc, 2) if i_dc is not None else None,
            inverter_status=inv_status,
            sensor_status=sens_status,
            days_since_cleaning=None,
            cumulative_rain_mm=None,
            is_stuck_sensor=False,
            evidence_notes=evidence_notes
        )
        return AnomalyEvent(
            asset_id=asset_id,
            start_time=start_t,
            end_time=end_t,
            actual_power_kw=round(mean_actual, 2),
            expected_power_kw=round(mean_expected, 2),
            residual_kw=round(mean_residual, 2),
            classification=AnomalyClassification.UNKNOWN_NEEDS_INVESTIGATION,
            severity=AnomalySeverity.INSUFFICIENT_EVIDENCE,
            confidence=None, # None reflects uncertainty
            evidence=bundle,
            model_version="solar_anomaly_v1.0",
            data_quality="UNVERIFIED"
        )
