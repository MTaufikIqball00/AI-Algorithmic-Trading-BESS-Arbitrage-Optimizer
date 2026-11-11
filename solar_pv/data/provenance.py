"""
Dataset Provenance and Metadata Tracking.
Maintains clear boundaries and lineage between real-world datasets and synthetic benchmarks.
"""
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional
import json
from datetime import datetime


class SourceType(str, Enum):
    REAL_HISTORICAL = "REAL_HISTORICAL"
    SYNTHETIC_SIMULATED = "SYNTHETIC_SIMULATED"
    BENCHMARK_HYBRID = "BENCHMARK_HYBRID"


@dataclass
class DatasetProvenance:
    dataset_name: str
    source_type: SourceType
    provider: str
    license: str
    citation: str
    creation_timestamp: str
    geographic_location: str
    sampling_interval_minutes: int
    timezone: str
    has_cleaning_records: bool
    has_maintenance_records: bool
    is_synthetic: bool
    generation_seed: Optional[int] = None
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["source_type"] = self.source_type.value
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetProvenance":
        data_copy = dict(data)
        if isinstance(data_copy.get("source_type"), str):
            data_copy["source_type"] = SourceType(data_copy["source_type"])
        return cls(**data_copy)


# Standard Provenance Registry for Solar PV Datasets
NREL_PVDAQ_PROVENANCE = DatasetProvenance(
    dataset_name="NREL_PVDAQ_Open_Dataset",
    source_type=SourceType.REAL_HISTORICAL,
    provider="National Renewable Energy Laboratory (NREL) / Open Energy Data Initiative (OEDI)",
    license="U.S. Government Work / Public Domain / CC0-compatible",
    citation="NREL Photovoltaic Data Acquisition (PVDAQ), OpenEI / AWS OEDI Data Lake, 2024.",
    creation_timestamp="2024-01-01T00:00:00Z",
    geographic_location="Golden, Colorado, USA (or regional test site)",
    sampling_interval_minutes=5,
    timezone="UTC",
    has_cleaning_records=False,
    has_maintenance_records=True,
    is_synthetic=False,
    notes="Real field sensor data with authentic pyranometer, module temperature, DC string and AC inverter measurements.",
)

SYNTHETIC_PV_PROVENANCE = DatasetProvenance(
    dataset_name="Deterministic_Physics_Synthetic_PV_Benchmark",
    source_type=SourceType.SYNTHETIC_SIMULATED,
    provider="AI-Algorithmic-Trading-BESS-Arbitrage-Optimizer Synthetic Generator",
    license="Apache 2.0 (Repository License)",
    citation="Synthetic PV Physical Simulation Engine with stochastic weather, soiling, and fault injection.",
    creation_timestamp=datetime.utcnow().isoformat() + "Z",
    geographic_location="Synthetically parameterized (34.05 deg N, -117.20 deg W)",
    sampling_interval_minutes=60,
    timezone="UTC",
    has_cleaning_records=True,
    has_maintenance_records=True,
    is_synthetic=True,
    generation_seed=42,
    notes="Generated using deterministic celestial mechanics, King cell temperature physics, soiling decay, and controlled sensor anomalies.",
)
