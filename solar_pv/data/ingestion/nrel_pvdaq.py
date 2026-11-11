"""
NREL PVDAQ / OEDI Real Open Dataset Ingestion Adapter.
Downloads and ingests verified open photovoltaic datasets from the National Renewable Energy Laboratory
Open Energy Data Initiative (OEDI) Data Lake, standardizing headers, units, and sentinel values.
"""
import os
import urllib.request
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from datetime import datetime

from ..provenance import NREL_PVDAQ_PROVENANCE, DatasetProvenance
from ..dictionary import DataQualityFlag, InverterStatus, SensorStatus
from ..validation.validator import PVDataValidator
from ..cleaning.cleaner import PVDataCleaner


class NRELPVDAQAdapter:
    """
    Ingests official NREL PVDAQ time-series CSVs.
    OEDI Data Lake S3 endpoint: https://oedi-data-lake.s3.amazonaws.com/pvdaq/
    """

    OEDI_BASE_URL = "https://oedi-data-lake.s3.amazonaws.com/pvdaq/csv/pvdata"

    def __init__(self, target_dir: str = "data/datasets/pv_real"):
        self.target_dir = target_dir
        os.makedirs(self.target_dir, exist_ok=True)
        self.validator = PVDataValidator(expected_interval_seconds=300) # 5-minute sampling
        self.cleaner = PVDataCleaner(max_interpolation_gap_steps=3)

    def fetch_sample_dataset(
        self,
        system_id: int = 10,
        year: int = 2000,
        month: int = 5,
        day: int = 10,
        timeout: int = 15
    ) -> Optional[pd.DataFrame]:
        """
        Fetch a verified single-day or multi-day sample from the public OEDI data lake.
        """
        url = f"{self.OEDI_BASE_URL}/system_id={system_id}/year={year}/month={month}/day={day}/system_{system_id}__date_{year}_{month:02d}_{day:02d}.csv"
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "BESS-SolarPV-Intelligence-Research/1.0"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                df_raw = pd.read_csv(resp)
                return self.standardize_nrel_dataframe(df_raw, system_id=f"NREL_SYS_{system_id}")
        except Exception as e:
            print(f"Notice: OEDI direct HTTP fetch failed ({e}). Fallback to local or synthetic.")
            return None

    def standardize_nrel_dataframe(
        self,
        df_raw: pd.DataFrame,
        system_id: str = "NREL_PVDAQ"
    ) -> pd.DataFrame:
        """
        Standardize raw NREL PVDAQ columns to unified Solar PV Data Dictionary schema.
        Handles NREL's dynamic sensor column naming (e.g. ac_power__423, poa_irradiance__421).
        """
        df = df_raw.copy()

        # Find timestamp column
        ts_col = None
        for col in ["measured_on", "timestamp", "Date-Time", "Date", "time"]:
            if col in df.columns:
                ts_col = col
                break

        if ts_col is None:
            raise ValueError(f"Could not find valid timestamp column in NREL CSV: {df.columns.tolist()}")

        df["dt"] = pd.to_datetime(df[ts_col])
        df = df.sort_values("dt").reset_index(drop=True)

        # Helper to find column matching prefix
        def find_col(prefix: str) -> Optional[str]:
            for c in df.columns:
                if c.startswith(prefix):
                    return c
            return None

        col_ac_power = find_col("ac_power")
        col_dc_power = find_col("dc_power")
        col_poa = find_col("poa_irradiance")
        col_amb_temp = find_col("ambient_temp")
        col_mod_temp = find_col("module_temp")
        col_dc_volt = find_col("dc_pos_voltage") or find_col("dc_voltage")
        col_dc_curr = find_col("dc_pos_current") or find_col("dc_current")

        def extract_series(col_name: Optional[str], default_val: float = 0.0) -> np.ndarray:
            if col_name and col_name in df.columns:
                s = pd.to_numeric(df[col_name], errors="coerce").values
                s = np.where(s <= -990.0, np.nan, s)
                return s
            return np.full(len(df), default_val)

        # In NREL PVDAQ, ac_power is typically reported in Watts or kW.
        # Check magnitude: if median peak > 5000, it is in Watts; convert to kW
        raw_ac = extract_series(col_ac_power)
        peak_ac = np.nanpercentile(raw_ac, 99) if np.any(~np.isnan(raw_ac)) else 0.0
        if peak_ac > 5000.0:
            power_kw = raw_ac / 1000.0
        else:
            power_kw = raw_ac

        poa = extract_series(col_poa)
        amb_t = extract_series(col_amb_temp, default_val=20.0)
        mod_t = extract_series(col_mod_temp, default_val=25.0)
        v_dc = extract_series(col_dc_volt)
        i_dc = extract_series(col_dc_curr)

        # Interval integration for energy (kWh)
        dt_diff_hours = df["dt"].diff().dt.total_seconds().fillna(300.0) / 3600.0
        energy_kwh = np.maximum(0.0, np.nan_to_num(power_kw) * dt_diff_hours)

        standardized = pd.DataFrame({
            "timestamp": df["dt"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "panel_id": system_id,
            "irradiance": poa,
            "plane_of_array_irradiance": poa,
            "panel_temperature": mod_t,
            "ambient_temperature": amb_t,
            "voltage": v_dc,
            "current": i_dc,
            "power": np.maximum(0.0, power_kw),
            "energy": energy_kwh,
            "humidity": 50.0,
            "wind_speed": 2.0,
            "cloud_cover": 0.0,
            "precipitation": 0.0,
            "inverter_status": InverterStatus.OPERATING_NORMAL.value,
            "sensor_status": SensorStatus.NORMAL.value,
            "data_quality": DataQualityFlag.VALID.value,
            "maintenance_timestamp": None,
            "cleaning_timestamp": None
        })

        # Apply cleaner
        cleaned_df, _ = self.cleaner.clean(standardized, record_lineage=False)
        return cleaned_df
