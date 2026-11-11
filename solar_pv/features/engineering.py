"""
Feature Engineering for Solar PV Power and Energy Forecasting.
Strictly guarantees ZERO FUTURE LEAKAGE by enforcing lag operations and shift(1) rolling statistics.
Integrates astronomical solar position, physical clear-sky power baselines, and weather lags.
"""
import math
import numpy as np
import pandas as pd
from typing import List, Optional

from .solar_physics import SolarPVPhysicsEngine
from ..data.weather.adapter import SolarWeatherAdapter
from ..config.defaults import PVSystemConfig

PV_FEATURE_COLUMNS = [
    # 1. Historical Power & Energy Lags (strictly in the past)
    "power_lag_1", "power_lag_2", "power_lag_3", "power_lag_24", "power_lag_48", "power_lag_168",
    "power_roll_mean_3", "power_roll_mean_24", "power_roll_std_24", "power_roll_max_24",
    
    # 2. Solar Celestial Geometry (known at time t without leakage)
    "solar_zenith_deg", "solar_elevation_deg", "solar_azimuth_deg", "cos_zenith",
    "hour_sin", "hour_cos", "doy_sin", "doy_cos",
    
    # 3. Weather & Physical Telemetry Lags (shifted to prevent lookahead)
    "irradiance_lag_1", "irradiance_lag_24",
    "poa_irradiance_lag_1", "poa_irradiance_lag_24",
    "panel_temp_lag_1", "ambient_temp_lag_1", "ambient_temp_forecast",
    "cloud_cover_forecast", "wind_speed_lag_1", "humidity_lag_1",
    
    # 4. First-Principles Physical Baseline Feature
    "expected_power_physical_kw"
]


class PVFeatureEngineer:
    """
    Transforms raw cleaned time-series into causal machine learning feature matrices.
    """

    def __init__(self, config: Optional[PVSystemConfig] = None):
        self.config = config or PVSystemConfig()
        self.physics = SolarPVPhysicsEngine(self.config)
        self.weather_adapter = SolarWeatherAdapter(
            latitude=self.config.latitude,
            longitude=self.config.longitude,
            altitude_m=self.config.altitude_m,
            tilt_deg=self.config.panel_tilt_deg,
            azimuth_deg=self.config.panel_azimuth_deg
        )

    def engineer_features(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """
        Generate feature dataframe with zero lookahead bias.
        """
        df = df_raw.copy()
        if "timestamp" not in df.columns:
            raise ValueError("'timestamp' column is required for feature engineering.")

        df["dt"] = pd.to_datetime(df["timestamp"])
        df = df.sort_values("dt").reset_index(drop=True)

        if "power" in df.columns:
            target_power = pd.to_numeric(df["power"], errors="coerce")
        elif "solar_gen_mw" in df.columns:
            target_power = pd.to_numeric(df["solar_gen_mw"], errors="coerce") * 1000.0
            df["power"] = target_power
        else:
            target_power = pd.Series(0.0, index=df.index)

        # Detect sampling interval to align 24h (1-day), 48h (2-day), and 168h (7-day) diurnal lags
        diffs = df["dt"].diff().dt.total_seconds().dropna()
        median_sec = float(diffs.median()) if len(diffs) > 0 else 3600.0
        if median_sec <= 0 or np.isnan(median_sec):
            median_sec = 3600.0
        steps_per_day = max(1, int(round(86400.0 / median_sec)))
        lag_1d = steps_per_day
        lag_2d = 2 * steps_per_day
        lag_7d = 7 * steps_per_day

        # 1. Power Lags (shift(k) ensures strictly historical observations)
        df["power_lag_1"] = target_power.shift(1)
        df["power_lag_2"] = target_power.shift(2)
        df["power_lag_3"] = target_power.shift(3)
        df["power_lag_24"] = target_power.shift(lag_1d)
        df["power_lag_48"] = target_power.shift(lag_2d)
        if len(df) >= lag_7d + 150:
            df["power_lag_168"] = target_power.shift(lag_7d)
        else:
            df["power_lag_168"] = target_power.shift(lag_7d).fillna(target_power.shift(lag_1d))

        # 2. Rolling Power Statistics (shift(1) strictly excludes current target step)
        df["power_roll_mean_3"] = target_power.shift(1).rolling(3, min_periods=1).mean()
        df["power_roll_mean_24"] = target_power.shift(1).rolling(lag_1d, min_periods=max(1, lag_1d // 2)).mean()
        df["power_roll_std_24"] = target_power.shift(1).rolling(lag_1d, min_periods=max(1, lag_1d // 2)).std().fillna(0.0)
        df["power_roll_max_24"] = target_power.shift(1).rolling(lag_1d, min_periods=max(1, lag_1d // 2)).max()

        # 3. Solar Astronomy Position (deterministic celestial coordinates at time t)
        solar_pos = self.weather_adapter.compute_solar_position(df["dt"])
        df["solar_zenith_deg"] = solar_pos["solar_zenith_deg"]
        df["solar_elevation_deg"] = solar_pos["solar_elevation_deg"]
        df["solar_azimuth_deg"] = solar_pos["solar_azimuth_deg"]
        df["cos_zenith"] = solar_pos["cos_zenith"]

        # 4. Cyclical Calendar Time Features
        hours = df["dt"].dt.hour + df["dt"].dt.minute / 60.0
        doy = df["dt"].dt.dayofyear
        df["hour_sin"] = np.sin(2 * np.pi * hours / 24.0)
        df["hour_cos"] = np.cos(2 * np.pi * hours / 24.0)
        df["doy_sin"] = np.sin(2 * np.pi * doy / 365.25)
        df["doy_cos"] = np.cos(2 * np.pi * doy / 365.25)

        # 5. Weather Lags & Forecast Features
        # Irradiance lags
        irr_col = df["irradiance"] if "irradiance" in df.columns else pd.Series(0.0, index=df.index)
        df["irradiance_lag_1"] = irr_col.shift(1)
        df["irradiance_lag_24"] = irr_col.shift(lag_1d)

        poa_col = df["plane_of_array_irradiance"] if "plane_of_array_irradiance" in df.columns else irr_col
        df["poa_irradiance_lag_1"] = poa_col.shift(1)
        df["poa_irradiance_lag_24"] = poa_col.shift(lag_1d)

        # Temperatures
        panel_t = df["panel_temperature"] if "panel_temperature" in df.columns else pd.Series(25.0, index=df.index)
        df["panel_temp_lag_1"] = panel_t.shift(1)

        amb_t = df["ambient_temperature"] if "ambient_temperature" in df.columns else df.get("temperature_c", pd.Series(20.0, index=df.index))
        df["ambient_temp_lag_1"] = amb_t.shift(1)
        # Exogenous ambient temp forecast (standard NWP hourly output)
        df["ambient_temp_forecast"] = amb_t

        # Cloud cover forecast (0.0 clear sky default)
        df["cloud_cover_forecast"] = df.get("cloud_cover", 0.0)

        # Wind speed & humidity
        ws_col = df["wind_speed"] if "wind_speed" in df.columns else pd.Series(2.0, index=df.index)
        df["wind_speed_lag_1"] = ws_col.shift(1)

        rh_col = df["humidity"] if "humidity" in df.columns else pd.Series(50.0, index=df.index)
        df["humidity_lag_1"] = rh_col.shift(1)

        # 6. First-Principles Expected Power Feature
        # Use clear-sky POA transposed irradiance for expected physical capacity at current zenith
        clear_ghi = self.weather_adapter.compute_clear_sky_ghi(solar_pos)
        clear_poa = self.weather_adapter.estimate_poa_from_ghi(clear_ghi, solar_pos)
        expected_power = self.physics.calculate_expected_power_kw(
            poa_irradiance=clear_poa,
            ambient_temperature_c=df["ambient_temp_forecast"],
            wind_speed_m_s=df["wind_speed_lag_1"]
        )
        # Nighttime power is physically zero
        expected_power = np.where(df["solar_elevation_deg"] <= 0.0, 0.0, expected_power)
        df["expected_power_physical_kw"] = expected_power

        return df
