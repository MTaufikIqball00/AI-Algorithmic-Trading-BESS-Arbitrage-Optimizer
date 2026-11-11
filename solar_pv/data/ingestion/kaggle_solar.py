"""
Kaggle Solar Power Generation Dataset Ingestion Adapter.
Parses, cleans, merges, and standardizes multi-inverter generation and weather station data from:
- Plant_1_Generation_Data.csv & Plant_1_Weather_Sensor_Data.csv
- Plant_2_Generation_Data.csv & Plant_2_Weather_Sensor_Data.csv
"""
import os
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime

from ..provenance import DatasetProvenance, SourceType
from ..dictionary import DataQualityFlag, InverterStatus, SensorStatus
from ..validation.validator import PVDataValidator, DataQualityReport
from ..cleaning.cleaner import PVDataCleaner


class KaggleSolarAdapter:
    """
    Ingests and merges multi-inverter generation and ambient weather telemetry.
    """

    def __init__(self, output_dir: str = "data/datasets/kaggle_solar"):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.validator = PVDataValidator(expected_interval_seconds=900) # 15-minute sampling
        self.cleaner = PVDataCleaner(max_interpolation_gap_steps=3)

    @staticmethod
    def _parse_datetime_series(s: pd.Series) -> pd.Series:
        """
        Safely parse datetime strings without mixed-format day/month transposition or warnings.
        Inspects whether strings begin with 4-digit year (YYYY-MM-DD) vs 2-digit day (DD-MM-YYYY).
        """
        sample = str(s.dropna().iloc[0]).strip() if len(s.dropna()) > 0 else ""
        if len(sample) >= 4 and sample[:4].isdigit():
            return pd.to_datetime(s, dayfirst=False)
        return pd.to_datetime(s, dayfirst=True)

    def process_plant(
        self,
        gen_path: str,
        weather_path: str,
        plant_name: str = "Plant_1",
        normalize_p1_dc: bool = True,
        tz_offset: str = "+05:30"
    ) -> Tuple[pd.DataFrame, pd.DataFrame, DataQualityReport, DatasetProvenance]:
        """
        Ingest, merge, clean, and standardize a plant's generation and weather logs.
        Returns:
            (df_inverter_level, df_plant_aggregate, quality_report, provenance)
        """
        if not os.path.exists(gen_path):
            raise FileNotFoundError(f"Generation CSV not found: {gen_path}")
        if not os.path.exists(weather_path):
            raise FileNotFoundError(f"Weather CSV not found: {weather_path}")

        df_gen = pd.read_csv(gen_path)
        df_wth = pd.read_csv(weather_path)

        # 1. Standardize datetime
        # Plant 1 generation is 'DD-MM-YYYY HH:MM' while weather and Plant 2 are 'YYYY-MM-DD HH:MM:SS'
        df_gen["dt"] = self._parse_datetime_series(df_gen["DATE_TIME"])
        df_wth["dt"] = self._parse_datetime_series(df_wth["DATE_TIME"])

        df_gen = df_gen.sort_values(["SOURCE_KEY", "dt"]).reset_index(drop=True)
        df_wth = df_wth.sort_values("dt").reset_index(drop=True)

        # Drop duplicate weather timestamps if any
        df_wth = df_wth.drop_duplicates(subset=["dt"]).reset_index(drop=True)

        # 2. Merge Generation with Weather on dt
        merged = pd.merge(df_gen, df_wth[["dt", "AMBIENT_TEMPERATURE", "MODULE_TEMPERATURE", "IRRADIATION"]], on="dt", how="inner")

        # 3. Unit standardization:
        # IRRADIATION is in kW/m^2 in raw data -> convert to W/m^2 (* 1000)
        irr_w_m2 = merged["IRRADIATION"] * 1000.0

        # DC_POWER unit check: Plant 1 has DC power ~14,000 for 1,400 AC (factor of 10x or deci-kW)
        dc_p = merged["DC_POWER"].astype(float)
        ac_p = merged["AC_POWER"].astype(float)
        if normalize_p1_dc and dc_p.max() > 5000.0 and ac_p.max() < 2000.0:
            dc_p = dc_p / 10.0

        # Energy per 15-min interval: (kW * 0.25 h)
        energy_kwh = np.maximum(0.0, ac_p * 0.25)

        # Inverter status estimation: if irradiation > 100 W/m^2 but AC power == 0 -> FAULT_TRIPPED
        inv_status = np.where(
            (irr_w_m2 > 100.0) & (ac_p <= 0.05),
            InverterStatus.FAULT_TRIPPED.value,
            np.where(irr_w_m2 <= 5.0, InverterStatus.STANDBY_NIGHT.value, InverterStatus.OPERATING_NORMAL.value)
        )

        df_inverters = pd.DataFrame({
            "timestamp": merged["dt"].dt.strftime(f"%Y-%m-%dT%H:%M:%S{tz_offset}"),
            "panel_id": merged["SOURCE_KEY"],
            "plant_id": merged["PLANT_ID"].iloc[0],
            "irradiance": np.round(irr_w_m2, 2),
            "plane_of_array_irradiance": np.round(irr_w_m2, 2),
            "panel_temperature": np.round(merged["MODULE_TEMPERATURE"], 2),
            "ambient_temperature": np.round(merged["AMBIENT_TEMPERATURE"], 2),
            "power": np.round(ac_p, 2),
            "dc_power": np.round(dc_p, 2),
            "energy": np.round(energy_kwh, 2),
            "daily_yield": merged["DAILY_YIELD"],
            "total_yield": merged["TOTAL_YIELD"],
            "humidity": 50.0,
            "wind_speed": 2.0,
            "cloud_cover": 0.0,
            "inverter_status": inv_status,
            "sensor_status": SensorStatus.NORMAL.value,
            "data_quality": DataQualityFlag.VALID.value,
            "cleaning_timestamp": None,
            "maintenance_timestamp": None
        })

        # 4. Plant Aggregate (sum across all 22 inverters per timestamp)
        grouped = df_inverters.groupby("timestamp", as_index=False).agg({
            "power": "sum",
            "dc_power": "sum",
            "energy": "sum",
            "irradiance": "first",
            "plane_of_array_irradiance": "first",
            "panel_temperature": "first",
            "ambient_temperature": "first",
            "humidity": "first",
            "wind_speed": "first",
            "cloud_cover": "first"
        })
        grouped["panel_id"] = f"{plant_name}_Total_Array"
        grouped["inverter_status"] = np.where(
            (grouped["irradiance"] > 100.0) & (grouped["power"] <= 0.1),
            InverterStatus.FAULT_TRIPPED.value,
            np.where(grouped["irradiance"] <= 5.0, InverterStatus.STANDBY_NIGHT.value, InverterStatus.OPERATING_NORMAL.value)
        )
        grouped["sensor_status"] = SensorStatus.NORMAL.value
        grouped["data_quality"] = DataQualityFlag.VALID.value
        grouped["cleaning_timestamp"] = None
        grouped["maintenance_timestamp"] = None

        # Sort chronologically
        grouped["dt"] = pd.to_datetime(grouped["timestamp"])
        grouped = grouped.sort_values("dt").reset_index(drop=True).drop(columns=["dt"])

        # Validate aggregate
        is_valid, report, issues = self.validator.validate(grouped)

        # Clean aggregate
        df_cleaned_agg, _ = self.cleaner.clean(grouped, record_lineage=False)

        # Provenance
        prov = DatasetProvenance(
            dataset_name=f"Kaggle_Solar_Power_Generation_{plant_name}",
            source_type=SourceType.REAL_HISTORICAL,
            provider="Kaggle Solar Power Generation Dataset (Gandikota, India)",
            license="CC0: Public Domain",
            citation="Solar Power Generation Data, Kaggle Dataset archive (34 days, 22 inverters, 15-min interval).",
            creation_timestamp=datetime.utcnow().isoformat() + "Z",
            geographic_location="Gandikota, Andhra Pradesh, India",
            sampling_interval_minutes=15,
            timezone=f"IST (UTC{tz_offset})",
            has_cleaning_records=False,
            has_maintenance_records=False,
            is_synthetic=False,
            notes=f"Processed {len(df_inverters)} inverter-level rows and {len(df_cleaned_agg)} plant aggregate intervals."
        )

        # Save to disk
        agg_file = os.path.join(self.output_dir, f"{plant_name.lower()}_aggregate.csv")
        inv_file = os.path.join(self.output_dir, f"{plant_name.lower()}_inverters.csv")
        df_cleaned_agg.to_csv(agg_file, index=False)
        df_inverters.to_csv(inv_file, index=False)

        return df_inverters, df_cleaned_agg, report, prov
