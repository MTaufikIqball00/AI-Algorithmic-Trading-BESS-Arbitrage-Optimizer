"""
Physics-Based Reproducible Synthetic Solar PV Dataset Generator.
Simulates realistic daily solar patterns, celestial mechanics, King thermal model,
inverter efficiency/clipping, soiling accumulation/washing, and equipment/sensor anomalies.
Strictly tags every record with SYNTHETIC_SIMULATED provenance.
"""
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
from datetime import datetime, timedelta, timezone

from ..dictionary import DataQualityFlag, InverterStatus, SensorStatus
from ..provenance import SYNTHETIC_PV_PROVENANCE
from ...config.defaults import (
    PVSystemConfig,
    STC_IRRADIANCE_W_PER_M2,
    STC_CELL_TEMP_C,
    DEFAULT_TEMP_COEFF_PMP
)


class SyntheticPVGenerator:
    """
    Deterministic synthetic time-series generator for PV analytics and unit testing.
    """

    def __init__(self, config: Optional[PVSystemConfig] = None, seed: int = 42):
        self.config = config or PVSystemConfig()
        self.seed = seed
        self.rng = np.random.RandomState(seed)

    def generate(
        self,
        start_date: str = "2024-01-01",
        days: int = 60,
        freq_minutes: int = 60,
        include_soiling_cycle: bool = True,
        include_anomalies: bool = True,
        annual_degradation_rate: float = 0.005 # 0.5% per year
    ) -> pd.DataFrame:
        """
        Generate synthetic time-series dataset.
        Returns a DataFrame adhering to the Solar PV data dictionary.
        """
        self.rng = np.random.RandomState(self.seed)
        tz_offset_hours = int(round(self.config.longitude / 15.0))
        local_tz = timezone(timedelta(hours=tz_offset_hours))
        ts_parsed = pd.to_datetime(start_date)
        start_dt = ts_parsed.tz_localize(local_tz) if ts_parsed.tzinfo is None else ts_parsed.tz_convert(local_tz)
        steps_per_day = max(1, 24 * 60 // freq_minutes)
        steps_per_hour = max(1, 60 // freq_minutes)
        total_steps = days * steps_per_day
        dt_index = pd.date_range(start=start_dt, periods=total_steps, freq=f"{freq_minutes}min", tz=local_tz)

        # Temporal parameters
        day_of_year = dt_index.dayofyear.values
        hour_float = dt_index.hour.values + dt_index.minute.values / 60.0

        # 1. Solar geometry & Clear-sky irradiance
        # Solar declination approximation (radians)
        declination = 0.409 * np.sin(2 * np.pi / 365.0 * (day_of_year - 81))
        lat_rad = math.radians(self.config.latitude)
        
        # Hour angle (radians)
        hour_angle = (hour_float - 12.0) * (np.pi / 12.0)
        
        # Solar elevation angle
        sin_elev = np.sin(lat_rad) * np.sin(declination) + np.cos(lat_rad) * np.cos(declination) * np.cos(hour_angle)
        elevation = np.degrees(np.arcsin(np.clip(sin_elev, -1.0, 1.0)))

        # Clear-sky Global Horizontal Irradiance (GHI) in W/m^2
        ghi_clear = np.where(elevation > 0, 1050.0 * np.maximum(0.0, sin_elev)**1.1, 0.0)

        # 2. Weather simulation: Cloud cover and Ambient Temperature
        # Markov-like cloud cover process
        base_cloud = 0.25 + 0.15 * np.sin(2 * np.pi * day_of_year / 365.0)
        cloud_noise = self.rng.beta(2, 5, size=total_steps)
        cloud_cover = np.clip(base_cloud + (cloud_noise - 0.28), 0.0, 1.0)

        # Actual GHI attenuated by clouds
        cloud_transmittance = 1.0 - 0.75 * (cloud_cover ** 1.5)
        ghi_actual = np.maximum(0.0, ghi_clear * cloud_transmittance + self.rng.normal(0, 5, size=total_steps))
        ghi_actual[elevation <= 0] = 0.0

        # Plane-of-array (POA) irradiance: higher than GHI in winter/equinox due to panel tilt
        tilt_factor = 1.0 + 0.22 * math.cos(math.radians(self.config.panel_tilt_deg))
        poa_irradiance = np.maximum(0.0, ghi_actual * tilt_factor)
        poa_irradiance[elevation <= 0] = 0.0

        # Ambient temperature (seasonal + diurnal sinusoid + noise)
        seasonal_temp = 15.0 + 12.0 * np.sin(2 * np.pi * (day_of_year - 105) / 365.0)
        diurnal_temp = 7.0 * np.sin(2 * np.pi * (hour_float - 8.0) / 24.0)
        ambient_temp = seasonal_temp + diurnal_temp + self.rng.normal(0, 1.5, size=total_steps)

        # Wind speed (m/s)
        wind_speed = np.clip(self.rng.weibull(2.0, size=total_steps) * 3.5, 0.1, 25.0)
        humidity = np.clip(55.0 - 15.0 * np.sin(2 * np.pi * (hour_float - 8.0) / 24.0) + self.rng.normal(0, 5, size=total_steps), 10.0, 95.0)

        # 3. King / Sandia Cell Temperature Model:
        # T_cell = T_amb + G_poa * exp(-a - b * wind_speed)
        # Using open-rack cell/module parameters: a = -3.56, b = -0.0750
        thermal_rise = poa_irradiance * np.exp(-3.56 - 0.075 * wind_speed)
        panel_temp = ambient_temp + thermal_rise

        # 4. Long-term degradation factor
        step_years = (np.arange(total_steps) * (freq_minutes / 60.0)) / 8760.0
        degradation_factor = 1.0 - annual_degradation_rate * step_years

        # 5. Soiling accumulation and cleaning event simulation
        soiling_factor = np.ones(total_steps)
        cleaning_timestamps = [None] * total_steps
        if include_soiling_cycle and days >= 20:
            dry_start_step = int(days * 0.35) * steps_per_day
            clean_step = min(total_steps - 1, int(days * 0.70) * steps_per_day)
            
            for s in range(dry_start_step, clean_step):
                day_offset = (s - dry_start_step) / steps_per_day
                soiling_factor[s] = max(0.85, 1.0 - 0.0035 * day_offset)
            
            # Cleaning event at step clean_step: restored to 0.995
            if clean_step < total_steps:
                cleaning_time_str = dt_index[clean_step].isoformat()
                cleaning_timestamps[clean_step] = cleaning_time_str
                for s in range(clean_step, total_steps):
                    soiling_factor[s] = 0.995

        # 6. Physical DC & AC Power Calculation
        # P_DC = P_STC * (G_POA / G_STC) * [1 + gamma * (T_cell - 25)] * soiling * degradation
        temp_loss = 1.0 + self.config.temp_coefficient * (panel_temp - STC_CELL_TEMP_C)
        temp_loss = np.clip(temp_loss, 0.60, 1.20)

        p_dc = self.config.rated_dc_power_kw * (poa_irradiance / STC_IRRADIANCE_W_PER_M2) * temp_loss * soiling_factor * degradation_factor
        p_dc = np.maximum(0.0, p_dc)

        # Inverter conversion and clipping
        p_ac = np.minimum(p_dc * self.config.inverter_efficiency, self.config.inverter_ac_power_kw)
        p_ac[elevation <= 0] = 0.0

        # DC Voltage and Current simulation
        # V_mp nominal ~ 600V, I_mp = P_dc / V_mp
        v_dc = np.where(poa_irradiance > 10.0, 620.0 - 1.8 * (panel_temp - 25.0) + self.rng.normal(0, 2, size=total_steps), 0.0)
        v_dc = np.maximum(0.0, v_dc)
        i_dc = np.divide(p_dc * 1000.0, v_dc, out=np.zeros_like(p_dc), where=v_dc > 50.0)
        i_dc = np.maximum(0.0, i_dc)

        # Status arrays
        inv_status = [InverterStatus.OPERATING_NORMAL.value] * total_steps
        sensor_status = [SensorStatus.NORMAL.value] * total_steps
        quality_flags = [DataQualityFlag.SYNTHETIC.value] * total_steps
        maintenance_timestamps = [None] * total_steps

        # Nighttime standby
        for i in range(total_steps):
            if elevation[i] <= 0:
                inv_status[i] = InverterStatus.STANDBY_NIGHT.value

        # 7. Configurable Anomaly Injection
        if include_anomalies and days >= 25:
            # Event A: Inverter trip between day 8 (11:00) and day 8 (15:00)
            trip_start = 8 * steps_per_day + 11 * steps_per_hour
            trip_end = 8 * steps_per_day + 15 * steps_per_hour
            if trip_end < total_steps:
                p_ac[trip_start:trip_end] = 0.0
                i_dc[trip_start:trip_end] = 0.0
                for s in range(trip_start, trip_end):
                    inv_status[s] = InverterStatus.FAULT_TRIPPED.value
                maintenance_timestamps[trip_end] = dt_index[trip_end].isoformat()

            # Event B: Sensor stuck reading on module temperature for 12 hours on day 20
            stuck_start = 20 * steps_per_day + 6 * steps_per_hour
            stuck_end = 20 * steps_per_day + 18 * steps_per_hour
            if stuck_end < total_steps:
                panel_temp[stuck_start:stuck_end] = panel_temp[stuck_start]
                for s in range(stuck_start, stuck_end):
                    sensor_status[s] = SensorStatus.STUCK.value

        # 8. Numerical Energy Integration (kWh)
        dt_hours = freq_minutes / 60.0
        energy_kwh = np.maximum(0.0, p_ac * dt_hours)

        df = pd.DataFrame({
            "timestamp": [t.isoformat() for t in dt_index],
            "panel_id": self.config.system_id,
            "irradiance": np.round(ghi_actual, 2),
            "plane_of_array_irradiance": np.round(poa_irradiance, 2),
            "panel_temperature": np.round(panel_temp, 2),
            "ambient_temperature": np.round(ambient_temp, 2),
            "voltage": np.round(v_dc, 2),
            "current": np.round(i_dc, 2),
            "power": np.round(p_ac, 2),
            "energy": np.round(energy_kwh, 2),
            "humidity": np.round(humidity, 1),
            "wind_speed": np.round(wind_speed, 2),
            "cloud_cover": np.round(cloud_cover, 3),
            "precipitation": 0.0,
            "inverter_status": inv_status,
            "sensor_status": sensor_status,
            "data_quality": quality_flags,
            "maintenance_timestamp": maintenance_timestamps,
            "cleaning_timestamp": cleaning_timestamps
        })

        return df
