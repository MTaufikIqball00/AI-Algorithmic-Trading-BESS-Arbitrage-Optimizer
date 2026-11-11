"""
Generic CSV Ingestion Adapter for custom PV sensor files.
Auto-maps flexible headers, validates against data dictionary, and generates provenance record.
"""
import os
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime

from ..dictionary import DATA_DICTIONARY, DataQualityFlag, InverterStatus, SensorStatus
from ..provenance import DatasetProvenance, SourceType
from ..validation.validator import PVDataValidator, DataQualityReport
from ..cleaning.cleaner import PVDataCleaner


class PVCSVImporter:
    """
    Standardized CSV importer for PV time-series datasets.
    """

    # Common aliases in industry SCADA logs
    HEADER_ALIASES = {
        "timestamp": ["timestamp", "time", "datetime", "date_time", "measured_on", "ts"],
        "power": ["power", "power_kw", "p_kw", "ac_power", "active_power", "p_mw", "solar_gen_mw"],
        "irradiance": ["irradiance", "ghi", "global_horizontal_irradiance", "solar_irradiance", "irr"],
        "plane_of_array_irradiance": ["plane_of_array_irradiance", "poa", "poa_irradiance", "tilted_irradiance"],
        "panel_temperature": ["panel_temperature", "cell_temperature", "module_temp", "t_cell", "temp_panel"],
        "ambient_temperature": ["ambient_temperature", "ambient_temp", "t_amb", "temperature_c", "air_temp"],
        "voltage": ["voltage", "v_dc", "dc_voltage", "voltage_v", "ac_voltage"],
        "current": ["current", "i_dc", "dc_current", "current_a", "ac_current"],
        "energy": ["energy", "energy_kwh", "kwh", "mwh", "yield"],
        "wind_speed": ["wind_speed", "wind_speed_m_s", "ws", "v_wind"],
        "cloud_cover": ["cloud_cover", "cloud", "cloudiness"],
        "precipitation": ["precipitation", "rainfall", "rain_mm"]
    }

    def __init__(self, target_dir: str = "data/datasets/pv_imported"):
        self.target_dir = target_dir
        os.makedirs(self.target_dir, exist_ok=True)
        self.validator = PVDataValidator()
        self.cleaner = PVDataCleaner()

    def import_csv(
        self,
        file_path: str,
        asset_id: str = "imported_array",
        is_synthetic: bool = False
    ) -> Tuple[pd.DataFrame, DataQualityReport, DatasetProvenance]:
        """
        Import a CSV file, standardize schema, validate, clean, and attach provenance.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"PV CSV file not found at {file_path}")

        df_raw = pd.read_csv(file_path)
        col_mapping = self._detect_columns(df_raw.columns.tolist())

        df_mapped = pd.DataFrame()
        for target_col, source_col in col_mapping.items():
            src_lower = source_col.lower().strip()
            if target_col == "power" and (src_lower.endswith("_mw") or src_lower == "p_mw"):
                df_mapped[target_col] = pd.to_numeric(df_raw[source_col], errors="coerce") * 1000.0
            elif target_col == "energy" and (src_lower.endswith("_mwh") or src_lower == "mwh"):
                df_mapped[target_col] = pd.to_numeric(df_raw[source_col], errors="coerce") * 1000.0
            else:
                df_mapped[target_col] = df_raw[source_col]

        # Ensure required 'timestamp' is present
        if "timestamp" not in df_mapped.columns:
            raise ValueError("Could not find a valid timestamp column in CSV.")

        # Ensure required 'power' is present
        if "power" not in df_mapped.columns:
            # Check if voltage and current exist to compute P = V * I / 1000
            if "voltage" in df_mapped.columns and "current" in df_mapped.columns:
                df_mapped["power"] = (df_mapped["voltage"] * df_mapped["current"]) / 1000.0
            else:
                raise ValueError("CSV must contain either 'power' or both 'voltage' and 'current'.")

        # Set asset ID
        df_mapped["panel_id"] = asset_id

        # Validate
        is_valid, report, issues = self.validator.validate(df_mapped)

        # Clean
        df_cleaned, _ = self.cleaner.clean(df_mapped, record_lineage=False)

        # Provenance
        prov = DatasetProvenance(
            dataset_name=os.path.basename(file_path),
            source_type=SourceType.SYNTHETIC_SIMULATED if is_synthetic else SourceType.REAL_HISTORICAL,
            provider="Custom User Import",
            license="User Provided",
            citation=f"Imported from {file_path}",
            creation_timestamp=datetime.utcnow().isoformat() + "Z",
            geographic_location="User Specified",
            sampling_interval_minutes=int(report.sampling_interval_median_seconds // 60) if report.sampling_interval_median_seconds > 0 else 60,
            timezone="UTC",
            has_cleaning_records="cleaning_timestamp" in df_cleaned.columns,
            has_maintenance_records="maintenance_timestamp" in df_cleaned.columns,
            is_synthetic=is_synthetic,
            notes=f"Auto-mapped {len(col_mapping)} columns. Quality score: {report.quality_score}/100."
        )

        return df_cleaned, report, prov

    def _detect_columns(self, input_cols: List[str]) -> Dict[str, str]:
        col_mapping = {}
        normalized_inputs = {c.lower().strip().replace(" ", "_"): c for c in input_cols}

        for std_name, aliases in self.HEADER_ALIASES.items():
            for alias in aliases:
                if alias in normalized_inputs:
                    col_mapping[std_name] = normalized_inputs[alias]
                    break

        return col_mapping
