"""
Evidence Tracking and Anomaly Classification Taxonomy for Solar Photovoltaic Systems.
Enforces that reductions in solar power are NEVER classified as soiling or equipment fault
without rigorous physical and historical evidence, explicitly supporting UNKNOWN / INSUFFICIENT EVIDENCE.
"""
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List


class AnomalyClassification(str, Enum):
    WEATHER_RELATED = "WEATHER_RELATED"
    POTENTIAL_SOILING = "POTENTIAL_SOILING"
    POTENTIAL_EQUIPMENT_FAULT = "POTENTIAL_EQUIPMENT_FAULT"
    SENSOR_FAULT = "SENSOR_FAULT"
    UNKNOWN_NEEDS_INVESTIGATION = "UNKNOWN_NEEDS_INVESTIGATION"


class AnomalySeverity(str, Enum):
    CRITICAL = "CRITICAL"         # Complete inverter trip, safety violation
    HIGH = "HIGH"                 # Major generation loss (>30% residual drop)
    MEDIUM = "MEDIUM"             # Moderate loss (15-30% loss)
    LOW = "LOW"                   # Minor loss (5-15% loss)
    MONITORING = "MONITORING"     # Borderline statistical drift
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass
class EvidenceBundle:
    irradiance_normalized_ratio: float       # P_actual / P_expected
    is_weather_explained: bool               # Low solar irradiance or heavy clouds
    cloud_cover: float                       # 0.0 to 1.0
    irradiance_w_per_m2: float               # Plane-of-array irradiance
    voltage_v: Optional[float]               # DC operating voltage
    current_a: Optional[float]               # DC operating current
    inverter_status: str                     # SunSpec / Modbus inverter code
    sensor_status: str                       # SCADA sensor diagnostic
    days_since_cleaning: Optional[int]       # Elapsed dry days
    cumulative_rain_mm: Optional[float]      # Recent precipitation
    is_stuck_sensor: bool                    # Flatline variance zero
    evidence_notes: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnomalyEvent:
    asset_id: str
    start_time: str
    end_time: str
    actual_power_kw: float
    expected_power_kw: float
    residual_kw: float
    classification: AnomalyClassification
    severity: AnomalySeverity
    confidence: Optional[float]              # None when evidence is insufficient
    evidence: EvidenceBundle
    model_version: str
    data_quality: str
    investigation_status: str = "OPEN"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["classification"] = self.classification.value
        d["severity"] = self.severity.value
        return d
