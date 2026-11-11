"""
Tests for PV Data Cleaning Engine.
Verifies sentinel replacement, gap interpolation boundaries, nighttime zero enforcement, and raw immutability.
"""
import pytest
import pandas as pd
import numpy as np

from solar_pv.data.cleaning.cleaner import PVDataCleaner
from solar_pv.data.dictionary import DataQualityFlag


def test_cleaner_replaces_sentinel_values():
    cleaner = PVDataCleaner(max_interpolation_gap_steps=0) # no interpolation
    df_raw = pd.DataFrame({
        "timestamp": ["2024-01-01T12:00:00Z", "2024-01-01T13:00:00Z"],
        "power": [500.0, -99999.0],
        "irradiance": [800.0, -999.0]
    })
    df_clean, lineage = cleaner.clean(df_raw, record_lineage=True)
    assert pd.isna(df_clean.loc[1, "power"]) or df_clean.loc[1, "power"] == 0.0
    assert pd.isna(df_clean.loc[1, "irradiance"]) or df_clean.loc[1, "irradiance"] == 0.0
    assert df_raw.loc[1, "power"] == -99999.0 # Raw DataFrame must remain unmodified


def test_cleaner_respects_max_interpolation_gap():
    # Only gaps <= 2 steps should be interpolated
    cleaner = PVDataCleaner(max_interpolation_gap_steps=2)
    # A gap of 5 steps
    df_raw = pd.DataFrame({
        "timestamp": [f"2024-01-01T{h:02d}:00:00Z" for h in range(8)],
        "power": [100.0, np.nan, np.nan, np.nan, np.nan, np.nan, 200.0, 210.0]
    })
    df_clean, _ = cleaner.clean(df_raw, record_lineage=False)
    # Step 1 and 2 should be interpolated, but step 3, 4, 5 must remain NaN
    assert pd.notna(df_clean.loc[1, "power"])
    assert pd.notna(df_clean.loc[2, "power"])
    assert pd.isna(df_clean.loc[3, "power"])
    assert pd.isna(df_clean.loc[4, "power"])


def test_cleaner_clamps_nighttime_noise():
    cleaner = PVDataCleaner()
    # Micro noise at night should be clamped to 0.0 kW
    df_raw = pd.DataFrame({
        "timestamp": ["2024-01-01T01:00:00Z", "2024-01-01T02:00:00Z"],
        "power": [0.02, -0.01],
        "irradiance": [0.0, 0.0]
    })
    df_clean, _ = cleaner.clean(df_raw, record_lineage=False)
    assert df_clean.loc[0, "power"] == 0.0
    assert df_clean.loc[1, "power"] == 0.0


def test_cleaner_caps_physical_bounds():
    cleaner = PVDataCleaner(cap_physical_bounds=True)
    df_raw = pd.DataFrame({
        "timestamp": ["2024-01-01T12:00:00Z"],
        "irradiance": [1650.0] # exceeds 1500 max
    })
    df_clean, _ = cleaner.clean(df_raw, record_lineage=False)
    assert df_clean.loc[0, "irradiance"] == 1500.0
    assert df_clean.loc[0, "data_quality"] == DataQualityFlag.CAPPED.value


def test_cleaner_preserves_high_capacity_plant_power_above_10mw():
    cleaner = PVDataCleaner(max_interpolation_gap_steps=0, enable_median_filter=False)
    df_raw = pd.DataFrame({
        "timestamp": ["2024-01-01T12:00:00Z", "2024-01-01T13:00:00Z"],
        "power": [28950.0, 9999.0],
        "energy": [7237.5, 15000.0],
        "irradiance": [950.0, 9999.0]
    })
    df_clean, _ = cleaner.clean(df_raw, record_lineage=False)
    assert df_clean.loc[0, "power"] == 28950.0
    assert df_clean.loc[1, "power"] == 9999.0
    assert df_clean.loc[1, "energy"] == 15000.0
    assert pd.isna(df_clean.loc[1, "irradiance"])

