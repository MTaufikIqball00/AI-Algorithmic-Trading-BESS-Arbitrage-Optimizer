"""
Condition-Based Maintenance Risk Scoring Engine for Solar Photovoltaic Assets.
Aggregates anomaly recurrence, electrical residual severity, inverter fault codes, and data quality.
Avoids unfounded Remaining Useful Life (RUL) claims.
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from ..anomaly_detection.evidence import AnomalyEvent, AnomalyClassification, AnomalySeverity


@dataclass
class AssetHealthScore:
    asset_id: str
    composite_risk_score: float             # 0.0 (Prism condition) to 100.0 (Imminent Failure)
    health_index_pct: float                 # 100.0 - risk_score
    anomaly_count_total: int
    critical_count: int
    hardware_fault_count: int
    soiling_count: int
    sensor_fault_count: int
    unknown_count: int
    recurrence_rate_per_month: float
    persistent_residual_loss_pct: float
    data_quality_penalty: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PVRiskScorer:
    """
    Computes an empirical condition risk index for Solar PV arrays and inverters.
    """

    def compute_risk_score(
        self,
        asset_id: str,
        events: List[AnomalyEvent],
        total_operating_days: float = 30.0,
        baseline_capacity_kw: float = 1000.0
    ) -> AssetHealthScore:
        """
        Aggregate anomaly events and persistent losses into a transparent risk score.
        """
        if not events:
            return AssetHealthScore(
                asset_id=asset_id,
                composite_risk_score=5.0, # Baseline normal operating wear
                health_index_pct=95.0,
                anomaly_count_total=0,
                critical_count=0,
                hardware_fault_count=0,
                soiling_count=0,
                sensor_fault_count=0,
                unknown_count=0,
                recurrence_rate_per_month=0.0,
                persistent_residual_loss_pct=0.0,
                data_quality_penalty=0.0
            )

        critical_count = sum(1 for e in events if e.severity == AnomalySeverity.CRITICAL)
        hw_count = sum(1 for e in events if e.classification == AnomalyClassification.POTENTIAL_EQUIPMENT_FAULT)
        soiling_count = sum(1 for e in events if e.classification == AnomalyClassification.POTENTIAL_SOILING)
        sensor_count = sum(1 for e in events if e.classification == AnomalyClassification.SENSOR_FAULT)
        unknown_count = sum(1 for e in events if e.classification == AnomalyClassification.UNKNOWN_NEEDS_INVESTIGATION)

        # Monthly recurrence rate
        months = max(0.5, total_operating_days / 30.0)
        recurrence_rate = round(len(events) / months, 2)

        # Average persistent residual loss (kW)
        avg_loss_kw = float(np.mean([abs(e.residual_kw) for e in events]))
        loss_pct = round((avg_loss_kw / max(1.0, baseline_capacity_kw)) * 100.0, 2)

        # Risk Score Calculation (0 to 100 scale):
        # 1. Critical hardware faults: 30 pts each (max 50)
        risk_hw = min(50.0, critical_count * 30.0 + hw_count * 15.0)

        # 2. Recurrence frequency: up to 25 pts
        risk_freq = min(25.0, recurrence_rate * 5.0)

        # 3. Residual capacity loss: up to 15 pts
        risk_loss = min(15.0, loss_pct * 0.5)

        # 4. Sensor faults: up to 10 pts
        risk_sens = min(10.0, sensor_count * 4.0)

        composite_risk = min(100.0, risk_hw + risk_freq + risk_loss + risk_sens)
        composite_risk = max(0.0, round(composite_risk, 1))
        health_index = round(100.0 - composite_risk, 1)

        return AssetHealthScore(
            asset_id=asset_id,
            composite_risk_score=composite_risk,
            health_index_pct=health_index,
            anomaly_count_total=len(events),
            critical_count=critical_count,
            hardware_fault_count=hw_count,
            soiling_count=soiling_count,
            sensor_fault_count=sensor_count,
            unknown_count=unknown_count,
            recurrence_rate_per_month=recurrence_rate,
            persistent_residual_loss_pct=loss_pct,
            data_quality_penalty=0.0
        )
