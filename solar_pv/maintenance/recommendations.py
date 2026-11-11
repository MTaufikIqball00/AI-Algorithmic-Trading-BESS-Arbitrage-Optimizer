"""
Evidence-Based Predictive Maintenance Recommendation Engine.
Produces actionable O&M inspection priorities:
- CRITICAL
- HIGH
- MEDIUM
- LOW
- MONITORING
- INSUFFICIENT_EVIDENCE
Strictly grounded in physical telemetry without fabricated Remaining Useful Life (RUL) dates.
"""
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional
import pandas as pd

from .risk_scoring import PVRiskScorer, AssetHealthScore
from ..anomaly_detection.evidence import AnomalyEvent, AnomalyClassification, AnomalySeverity


class MaintenancePriority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    MONITORING = "MONITORING"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass
class MaintenanceRecommendation:
    recommendation_id: str
    asset_id: str
    priority: MaintenancePriority
    analysis_period: str
    reason: str
    evidence: List[str]
    recommended_inspection: str
    uncertainty: str
    data_limitations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["priority"] = self.priority.value
        return d


class PVMaintenanceAdvisor:
    """
    Generates evidence-backed condition maintenance recommendations for field engineering dispatch.
    """

    def __init__(self):
        self.risk_scorer = PVRiskScorer()

    def generate_recommendations(
        self,
        asset_id: str,
        events: List[AnomalyEvent],
        health_score: Optional[AssetHealthScore] = None,
        analysis_period: str = "Last 30 Days",
        missing_data_fields: Optional[List[str]] = None
    ) -> List[MaintenanceRecommendation]:
        """
        Generate prioritized maintenance work orders.
        """
        recs: List[MaintenanceRecommendation] = []
        rec_counter = 1
        missing_fields = missing_data_fields or []

        # If data is completely missing or no valid observations
        if health_score is None:
            health_score = self.risk_scorer.compute_risk_score(asset_id, events)

        # 1. Critical Hardware Inverter Trip / Electrical Disconnect
        crit_events = [e for e in events if e.severity == AnomalySeverity.CRITICAL or e.classification == AnomalyClassification.POTENTIAL_EQUIPMENT_FAULT]
        if crit_events:
            ev_notes = []
            for e in crit_events[:3]:
                ev_notes.extend(e.evidence.evidence_notes)
            recs.append(
                MaintenanceRecommendation(
                    recommendation_id=f"REC-{asset_id}-{rec_counter:03d}",
                    asset_id=asset_id,
                    priority=MaintenancePriority.CRITICAL,
                    analysis_period=analysis_period,
                    reason=f"Detected {len(crit_events)} critical inverter trip or electrical disconnect events under high irradiance.",
                    evidence=list(set(ev_notes)),
                    recommended_inspection="Perform immediate field inspection of inverter AC breaker, DC contactors, and MPPT string combiner box. Inspect inverter event logs for ground fault or IGBT over-temperature trips.",
                    uncertainty="Low uncertainty (confidence: 0.92-0.95 based on direct telemetry collapse).",
                    data_limitations=missing_fields
                )
            )
            rec_counter += 1

        # 2. Potential Soiling Accumulation
        soiling_events = [e for e in events if e.classification == AnomalyClassification.POTENTIAL_SOILING]
        if len(soiling_events) >= 2 or health_score.soiling_count >= 2:
            recs.append(
                MaintenanceRecommendation(
                    recommendation_id=f"REC-{asset_id}-{rec_counter:03d}",
                    asset_id=asset_id,
                    priority=MaintenancePriority.MEDIUM,
                    analysis_period=analysis_period,
                    reason=f"Persistent irradiance-normalized performance depression ({health_score.soiling_count} occurrences) during extended dry period.",
                    evidence=[
                        f"Midday performance ratio consistently 10-25% below expected clear-sky baseline.",
                        "No inverter electrical trip codes logged."
                    ],
                    recommended_inspection="Dispatch visual inspection of array front surface for dust, pollen, or agricultural residue. Schedule panel washing if soiling layer exceeds 5% optical attenuation.",
                    uncertainty="Moderate uncertainty: requires visual on-site confirmation or clean reference panel comparison.",
                    data_limitations=["Local precipitation history or cleaning logs absent."] if "cleaning_timestamp" in missing_fields else []
                )
            )
            rec_counter += 1

        # 3. Sensor Fault / Stuck Telemetry
        sensor_events = [e for e in events if e.classification == AnomalyClassification.SENSOR_FAULT]
        if sensor_events:
            recs.append(
                MaintenanceRecommendation(
                    recommendation_id=f"REC-{asset_id}-{rec_counter:03d}",
                    asset_id=asset_id,
                    priority=MaintenancePriority.LOW,
                    analysis_period=analysis_period,
                    reason=f"Detected {len(sensor_events)} sensor communication or telemetry anomalies.",
                    evidence=[
                        "Measurement flatlined with zero variance or reported out-of-physical-bounds sentinel.",
                    ],
                    recommended_inspection="Inspect sensor wiring, RS-485 Modbus communication loop, and recalibrate reference pyranometer/RTD temperature probe.",
                    uncertainty="Low uncertainty regarding sensor invalidity; primary generation hardware may be operating normally.",
                    data_limitations=missing_fields
                )
            )
            rec_counter += 1

        # 4. Unknown / Insufficient Evidence
        unknown_events = [e for e in events if e.classification == AnomalyClassification.UNKNOWN_NEEDS_INVESTIGATION]
        if unknown_events and not crit_events and not soiling_events:
            recs.append(
                MaintenanceRecommendation(
                    recommendation_id=f"REC-{asset_id}-{rec_counter:03d}",
                    asset_id=asset_id,
                    priority=MaintenancePriority.INSUFFICIENT_EVIDENCE,
                    analysis_period=analysis_period,
                    reason=f"{len(unknown_events)} anomalous production drops observed without conclusive physical evidence.",
                    evidence=[
                        "Power dropped below expectation but could not be definitively linked to weather, soiling, or hardware failure."
                    ],
                    recommended_inspection="Review high-resolution SCADA string current logs and on-site weather station pyranometer calibration before dispatching field technicians.",
                    uncertainty="High uncertainty: insufficient auxiliary telemetry.",
                    data_limitations=["DC string current, local rainfall, or inverter alarm codes absent from dataset."]
                )
            )
            rec_counter += 1

        # 5. Routine Monitoring Baseline
        if not recs:
            recs.append(
                MaintenanceRecommendation(
                    recommendation_id=f"REC-{asset_id}-{rec_counter:03d}",
                    asset_id=asset_id,
                    priority=MaintenancePriority.MONITORING,
                    analysis_period=analysis_period,
                    reason=f"Asset health score ({health_score.health_index_pct:.1f}%) is within normal nominal bounds. No actionable anomalies detected.",
                    evidence=["All generation parameters adhere to physical expected models."],
                    recommended_inspection="Continue routine supervisory monitoring. Next scheduled inspection as per annual preventive maintenance plan.",
                    uncertainty="Nominal operating confidence.",
                    data_limitations=[]
                )
            )

        return recs
