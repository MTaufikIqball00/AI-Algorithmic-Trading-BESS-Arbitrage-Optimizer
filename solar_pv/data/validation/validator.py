"""
Solar PV Data Validation Engine.
Validates timestamp monotonic ordering, duplicate records, physical range limits,
sensor continuity, sampling intervals, and produces structured data quality metrics.
"""
from dataclasses import dataclass, asdict
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np

from ..dictionary import DATA_DICTIONARY, DataQualityFlag
from ...config.defaults import (
    MIN_IRRADIANCE, MAX_IRRADIANCE,
    MIN_AMBIENT_TEMP_C, MAX_AMBIENT_TEMP_C,
    MIN_CELL_TEMP_C, MAX_CELL_TEMP_C,
    MIN_WIND_SPEED_M_S, MAX_WIND_SPEED_M_S,
    MIN_RELATIVE_HUMIDITY, MAX_RELATIVE_HUMIDITY
)


@dataclass
class DataQualityReport:
    total_records: int
    start_timestamp: Optional[str]
    end_timestamp: Optional[str]
    is_chronological: bool
    duplicate_timestamps: int
    missing_timestamp_count: int
    completeness_pct: float
    field_missing_counts: Dict[str, int]
    field_missing_pct: Dict[str, float]
    field_out_of_bounds_counts: Dict[str, int]
    nighttime_zero_count: int
    sampling_interval_median_seconds: float
    sampling_interval_irregular_count: int
    quality_score: float # 0.0 to 100.0 scale

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PVDataValidator:
    """
    Validates PV time-series datasets against strict physical and temporal rules.
    Guarantees raw data immutability.
    """

    def __init__(self, expected_interval_seconds: Optional[float] = None):
        self.expected_interval_seconds = expected_interval_seconds

    def validate(self, df_raw: pd.DataFrame) -> Tuple[bool, DataQualityReport, List[str]]:
        """
        Run complete validation suite.
        Returns:
            (is_valid, report, issue_messages)
        """
        if df_raw.empty:
            empty_report = DataQualityReport(
                total_records=0,
                start_timestamp=None,
                end_timestamp=None,
                is_chronological=False,
                duplicate_timestamps=0,
                missing_timestamp_count=0,
                completeness_pct=0.0,
                field_missing_counts={},
                field_missing_pct={},
                field_out_of_bounds_counts={},
                nighttime_zero_count=0,
                sampling_interval_median_seconds=0.0,
                sampling_interval_irregular_count=0,
                quality_score=0.0
            )
            return False, empty_report, ["Dataset is completely empty."]

        issues: List[str] = []
        df = df_raw.copy()

        # 1. Timestamp validation
        if "timestamp" not in df.columns:
            return False, None, ["Critical error: 'timestamp' column is missing from dataset."]

        # Check datetime parseability
        try:
            timestamps = pd.to_datetime(df["timestamp"])
        except Exception as e:
            return False, None, [f"Critical error: Failed to parse timestamps: {e}"]

        total_records = len(df)
        null_ts_count = int(timestamps.isna().sum())
        if null_ts_count > 0:
            issues.append(f"Found {null_ts_count} null timestamps.")

        # Check chronological ordering
        is_chronological = bool(timestamps.is_monotonic_increasing)
        if not is_chronological:
            issues.append("Timestamps are not monotonically increasing. Sorting required.")

        # Check duplicate timestamps
        duplicate_timestamps = int(timestamps.duplicated().sum())
        if duplicate_timestamps > 0:
            issues.append(f"Found {duplicate_timestamps} duplicate timestamps.")

        # 2. Sampling interval analysis
        sorted_ts = timestamps.dropna().sort_values()
        diffs = sorted_ts.diff().dt.total_seconds().dropna()
        if len(diffs) > 0:
            median_interval = float(diffs.median())
            expected_dt = self.expected_interval_seconds or median_interval
            # Count intervals differing by more than 10% from median
            irregular_dt_count = int(((diffs < 0.9 * expected_dt) | (diffs > 1.1 * expected_dt)).sum())
            if irregular_dt_count > 0:
                issues.append(f"Found {irregular_dt_count} time gaps/irregular intervals exceeding +/-10% of median {median_interval}s.")
        else:
            median_interval = 0.0
            irregular_dt_count = 0

        # 3. Missing values and out-of-bounds counts per field
        field_missing_counts: Dict[str, int] = {}
        field_missing_pct: Dict[str, float] = {}
        field_out_of_bounds: Dict[str, int] = {}

        high_capacity_cols = {"power", "dc_power", "energy", "daily_yield", "total_yield"}

        for col in df.columns:
            if col == "timestamp":
                continue
            series = pd.to_numeric(df[col], errors="coerce")
            missing_count = int(series.isna().sum())
            # Also treat common sentinel values (-99999, -999, 9999) as missing
            if col in high_capacity_cols:
                sentinel_mask = (series == -99999.0) | (series == -9999.0) | (series == -999.0)
            else:
                sentinel_mask = (series == -99999.0) | (series == -9999.0) | (series == -999.0) | (series == 9999.0)
            sentinel_count = int(sentinel_mask.sum())
            total_missing = missing_count + sentinel_count
            field_missing_counts[col] = total_missing
            field_missing_pct[col] = round((total_missing / total_records) * 100.0, 2)

            # Check bounds if in dictionary
            if col in DATA_DICTIONARY:
                fdef = DATA_DICTIONARY[col]
                valid_series = series[~series.isna() & ~sentinel_mask]
                oob_count = 0
                if fdef.min_value is not None:
                    oob_count += int((valid_series < fdef.min_value - 1e-4).sum())
                if fdef.max_value is not None:
                    oob_count += int((valid_series > fdef.max_value + 1e-4).sum())
                field_out_of_bounds[col] = oob_count
                if oob_count > 0:
                    issues.append(f"Field '{col}' has {oob_count} values outside physical range [{fdef.min_value}, {fdef.max_value} {fdef.unit}].")

        # 4. Nighttime zero analysis
        # When irradiance is 0 or sun is down, power is normally 0 kW
        nighttime_zeros = 0
        if "power" in df.columns:
            p_series = pd.to_numeric(df["power"], errors="coerce").fillna(0)
            if "irradiance" in df.columns:
                irr_series = pd.to_numeric(df["irradiance"], errors="coerce").fillna(0)
                nighttime_zeros = int(((irr_series < 5.0) & (p_series <= 0.05)).sum())
            else:
                nighttime_zeros = int((p_series <= 0.001).sum())

        # 5. Overall quality score computation (100 = perfect, 0 = unusable)
        # Penalties:
        # - non-chronological: -10
        # - duplicates: -10 * (dup_count / total)
        # - missing critical fields (power): -30 * (miss / total)
        # - out of bounds: -20 * (oob / total)
        score = 100.0
        if not is_chronological:
            score -= 10.0
        if duplicate_timestamps > 0:
            score -= min(15.0, (duplicate_timestamps / total_records) * 100.0)
        power_miss_pct = field_missing_pct.get("power", 0.0)
        score -= (power_miss_pct * 0.3)
        total_oob = sum(field_out_of_bounds.values())
        score -= min(20.0, (total_oob / max(1, total_records * len(df.columns))) * 100.0)
        quality_score = max(0.0, min(100.0, round(score, 2)))

        start_ts = str(sorted_ts.iloc[0]) if len(sorted_ts) > 0 else None
        end_ts = str(sorted_ts.iloc[-1]) if len(sorted_ts) > 0 else None
        avg_missing = float(np.mean(list(field_missing_pct.values()))) if field_missing_pct else 0.0
        completeness = max(0.0, min(100.0, round(100.0 - avg_missing, 2)))

        report = DataQualityReport(
            total_records=total_records,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            is_chronological=is_chronological,
            duplicate_timestamps=duplicate_timestamps,
            missing_timestamp_count=null_ts_count,
            completeness_pct=completeness,
            field_missing_counts=field_missing_counts,
            field_missing_pct=field_missing_pct,
            field_out_of_bounds_counts=field_out_of_bounds,
            nighttime_zero_count=nighttime_zeros,
            sampling_interval_median_seconds=median_interval,
            sampling_interval_irregular_count=irregular_dt_count,
            quality_score=quality_score
        )

        is_valid = (null_ts_count == 0) and (quality_score >= 50.0)
        return is_valid, report, issues
