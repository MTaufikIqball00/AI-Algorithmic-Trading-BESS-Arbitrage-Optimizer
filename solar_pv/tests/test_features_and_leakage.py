"""
Tests for Feature Engineering and Lookahead Leakage Prevention.
"""
import pytest
import pandas as pd
import numpy as np

from solar_pv.features.engineering import PVFeatureEngineer, PV_FEATURE_COLUMNS
from solar_pv.data.weather.adapter import SolarWeatherAdapter


def test_zero_lookahead_leakage():
    engineer = PVFeatureEngineer()
    dates = pd.date_range("2024-06-01", periods=48, freq="1h", tz="UTC")
    df_raw = pd.DataFrame({
        "timestamp": [d.isoformat() for d in dates],
        "power": [float(h * 10) for h in range(48)],
        "irradiance": [float(h * 20) for h in range(48)],
        "ambient_temperature": [20.0] * 48
    })
    df_feat = engineer.engineer_features(df_raw)

    # 1. Verify power_lag_1 at row t strictly equals power at row t-1
    for t in range(1, len(df_feat)):
        assert df_feat.loc[t, "power_lag_1"] == df_raw.loc[t - 1, "power"]

    # 2. Verify rolling mean excludes current target step t
    # At row 10, mean of past 3 steps should be mean of rows 7, 8, 9
    expected_mean_3 = (df_raw.loc[7, "power"] + df_raw.loc[8, "power"] + df_raw.loc[9, "power"]) / 3.0
    assert abs(df_feat.loc[10, "power_roll_mean_3"] - expected_mean_3) < 1e-4


def test_astronomical_solar_position():
    adapter = SolarWeatherAdapter(latitude=34.05, longitude=-117.20)
    # Noon vs Midnight UTC offset check
    dt_series = pd.Series([
        pd.to_datetime("2024-06-21T20:00:00Z"), # Summer solstice midday in California (approx noon local)
        pd.to_datetime("2024-06-21T08:00:00Z")  # Nighttime in California (approx midnight local)
    ])
    pos = adapter.compute_solar_position(dt_series)

    # Midday elevation should be high (> 60 degrees)
    assert pos.loc[0, "solar_elevation_deg"] > 60.0
    # Midnight elevation must be negative (< 0 degrees)
    assert pos.loc[1, "solar_elevation_deg"] < 0.0
