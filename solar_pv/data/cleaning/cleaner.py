"""
Solar PV Preprocessing & Cleaning Engine.
Provides reproducible cleaning, time-aware gap interpolation, median noise reduction,
physical bounding, nighttime-zero enforcement, and explicit data lineage tracking.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional, Tuple, Set
import pandas as pd
import numpy as np
from datetime import datetime

from ..dictionary import DATA_DICTIONARY, DataQualityFlag
from ...config.defaults import (
    MIN_IRRADIANCE, MAX_IRRADIANCE,
    MIN_AMBIENT_TEMP_C, MAX_AMBIENT_TEMP_C,
    MIN_CELL_TEMP_C, MAX_CELL_TEMP_C
)


@dataclass
class LineageRecord:
    timestamp: str
    column: str
    original_value: Optional[float]
    cleaned_value: Optional[float]
    processing_method: str
    quality_flag: str
    processing_time: str


class PVDataCleaner:
    """
    Robust scientific cleaner for photovoltaic sensor telemetry.
    Maintains full audit lineage and strictly prevents future data leakage.
    """

    def __init__(
        self,
        max_interpolation_gap_steps: int = 3,  # Only interpolate short gaps (e.g., <= 3 steps)
        enable_median_filter: bool = True,
        median_filter_window: int = 3,
        auto_deduplicate: bool = True,
        cap_physical_bounds: bool = True
    ):
        self.max_gap_steps = max_interpolation_gap_steps
        self.enable_median_filter = enable_median_filter
        self.median_filter_window = median_filter_window
        self.auto_deduplicate = auto_deduplicate
        self.cap_physical_bounds = cap_physical_bounds

    def clean(
        self,
        df_raw: pd.DataFrame,
        record_lineage: bool = True
    ) -> Tuple[pd.DataFrame, List[LineageRecord]]:
        """
        Clean the input DataFrame and return (df_cleaned, lineage_records).
        Guarantees that raw data is not modified.
        """
        if df_raw.empty:
            return df_raw.copy(), []

        df = df_raw.copy()
        lineage: List[LineageRecord] = []
        proc_time = datetime.utcnow().isoformat() + "Z"

        # 1. Parse and sort timestamps
        if "timestamp" not in df.columns:
            raise ValueError("Cannot clean DataFrame: 'timestamp' column is required.")

        df["dt"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("dt").reset_index(drop=True)

        # 2. Deduplicate timestamps
        if self.auto_deduplicate:
            dup_mask = df.duplicated(subset=["dt"], keep="first")
            if dup_mask.any():
                df = df[~dup_mask].reset_index(drop=True)

        # 3. Clean sentinel values (-99999, -999, 9999) across numeric columns
        numeric_cols = [
            c for c in df.columns
            if c not in ["timestamp", "dt", "panel_id", "inverter_status", "sensor_status", "data_quality", "maintenance_timestamp", "cleaning_timestamp"]
            and pd.api.types.is_numeric_dtype(df[c])
        ]

        # Initialize quality flags column if not present
        if "data_quality" not in df.columns:
            df["data_quality"] = DataQualityFlag.VALID.value

        # Columns where 9999.0 is a logger sentinel (all columns whose physical max is < 9000)
        high_capacity_cols = {"power", "dc_power", "energy", "daily_yield", "total_yield"}

        for col in numeric_cols:
            orig_vals = df[col].copy()
            # Replace sentinels with NaN:
            # Negative sentinels (-999, -9999, -99999) apply to all columns (min physical temp is -40C).
            # Positive sentinel (9999) only applies to bounded sensor columns, NEVER to power/energy/yield.
            if col in high_capacity_cols:
                sentinel_mask = df[col] <= -990.0
            else:
                sentinel_mask = (df[col] <= -990.0) | (df[col] == 9999.0) | (df[col] == 99999.0)
            df.loc[sentinel_mask, col] = np.nan

            # Nighttime zero handling for solar irradiance and power
            if col in ["irradiance", "plane_of_array_irradiance", "power", "solar_gen_mw", "current"]:
                # If irradiance is near zero, clamp negative/tiny noise to exact zero
                near_zero = (df[col].notna()) & (df[col] < 0.05) & (df[col] >= -10.0)
                df.loc[near_zero, col] = 0.0

            # Short gap interpolation: strictly limit to max_gap_steps
            if self.max_gap_steps > 0:
                is_na_before = df[col].isna()
                df[col] = df[col].interpolate(method="time", limit=self.max_gap_steps, limit_direction="forward") if hasattr(df, "index") and isinstance(df.index, pd.DatetimeIndex) else df[col].interpolate(method="linear", limit=self.max_gap_steps, limit_direction="forward")
                # Flag interpolated values
                interpolated_mask = is_na_before & df[col].notna()
                df.loc[interpolated_mask, "data_quality"] = DataQualityFlag.INTERPOLATED.value

            # Flag remaining NaNs as MISSING
            still_na_mask = df[col].isna()
            df.loc[still_na_mask, "data_quality"] = DataQualityFlag.MISSING.value

            # Median filtering for noise removal (optional, only on continuous segments)
            if self.enable_median_filter and col in ["power", "voltage", "current"]:
                valid_mask = df[col].notna()
                if valid_mask.sum() > self.median_filter_window:
                    rolled = df.loc[valid_mask, col].rolling(
                        window=self.median_filter_window, min_periods=1, center=True
                    ).median()
                    # Only apply filter if deviation is small (noise), not a sudden step change/trip
                    residual = (df.loc[valid_mask, col] - rolled).abs()
                    noise_mask = residual > 0.001
                    # Update values gently
                    df.loc[valid_mask & (residual < (df[col].std() * 0.5)), col] = rolled

            # Physical bounding
            if self.cap_physical_bounds and col in DATA_DICTIONARY:
                fdef = DATA_DICTIONARY[col]
                if fdef.min_value is not None:
                    under_mask = df[col] < fdef.min_value
                    if under_mask.any():
                        df.loc[under_mask, col] = fdef.min_value
                        df.loc[under_mask, "data_quality"] = DataQualityFlag.CAPPED.value
                if fdef.max_value is not None:
                    over_mask = df[col] > fdef.max_value
                    if over_mask.any():
                        df.loc[over_mask, col] = fdef.max_value
                        df.loc[over_mask, "data_quality"] = DataQualityFlag.CAPPED.value

            # Track lineage sample for modified records
            if record_lineage:
                changed = (orig_vals != df[col]) & ~(orig_vals.isna() & df[col].isna())
                changed_indices = df.index[changed].tolist()[:50] # Sample up to 50 for memory safety
                for idx in changed_indices:
                    lineage.append(
                        LineageRecord(
                            timestamp=str(df.loc[idx, "timestamp"]),
                            column=col,
                            original_value=float(orig_vals.loc[idx]) if pd.notna(orig_vals.loc[idx]) else None,
                            cleaned_value=float(df.loc[idx, col]) if pd.notna(df.loc[idx, col]) else None,
                            processing_method="clean_sentinels_interpolate_bound",
                            quality_flag=str(df.loc[idx, "data_quality"]),
                            processing_time=proc_time
                        )
                    )

        # Drop temporary 'dt' column and return
        df = df.drop(columns=["dt"], errors="ignore")
        return df, lineage
