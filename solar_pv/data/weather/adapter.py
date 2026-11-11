"""
Solar Weather Adapter and Astronomy Geometry Engine.
Computes solar zenith, azimuth, elevation, clear-sky irradiance, and transposition to Plane-of-Array (POA).
Prevents weather forecast lookahead leakage.
"""
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional


class SolarWeatherAdapter:
    """
    Computes celestial mechanics and physical irradiance decomposition without external web dependencies.
    """

    def __init__(
        self,
        latitude: float = 34.05,
        longitude: float = -117.20,
        altitude_m: float = 300.0,
        tilt_deg: float = 25.0,
        azimuth_deg: float = 180.0, # 180 = South facing
        ground_albedo: float = 0.20
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.altitude_m = altitude_m
        self.tilt_deg = tilt_deg
        self.azimuth_deg = azimuth_deg
        self.ground_albedo = ground_albedo

    def compute_solar_position(self, dt: pd.Series) -> pd.DataFrame:
        """
        Calculate solar zenith, elevation, and azimuth angles using astronomical algorithms (Spencer/Michalsky).
        Input dt must be a timezone-aware or UTC pandas DatetimeIndex / Series.
        """
        dt_series = pd.to_datetime(dt)
        if dt_series.dt.tz is None:
            # Assume UTC if tz naive
            dt_utc = dt_series
        else:
            dt_utc = dt_series.dt.tz_convert("UTC")

        day_of_year = dt_utc.dt.dayofyear
        fractional_year = 2.0 * math.pi / 365.0 * (day_of_year - 1 + (dt_utc.dt.hour - 12) / 24.0)

        # Equation of time (minutes)
        eot = 229.18 * (
            0.000075 + 0.001868 * np.cos(fractional_year)
            - 0.032077 * np.sin(fractional_year)
            - 0.014615 * np.cos(2 * fractional_year)
            - 0.040849 * np.sin(2 * fractional_year)
        )

        # Solar declination angle (radians)
        declination = (
            0.006918
            - 0.399912 * np.cos(fractional_year)
            + 0.070257 * np.sin(fractional_year)
            - 0.006758 * np.cos(2 * fractional_year)
            + 0.000907 * np.sin(2 * fractional_year)
            - 0.002697 * np.cos(3 * fractional_year)
            + 0.00148 * np.sin(3 * fractional_year)
        )

        # True solar time (minutes from midnight)
        time_offset = eot + 4.0 * self.longitude
        solar_time_min = dt_utc.dt.hour * 60.0 + dt_utc.dt.minute + dt_utc.dt.second / 60.0 + time_offset
        solar_time_min = solar_time_min % 1440.0

        # Hour angle (degrees and radians)
        hour_angle_deg = (solar_time_min / 4.0) - 180.0
        hour_angle_rad = np.radians(hour_angle_deg)

        lat_rad = math.radians(self.latitude)

        # Solar zenith angle (radians)
        cos_zenith = np.sin(lat_rad) * np.sin(declination) + np.cos(lat_rad) * np.cos(declination) * np.cos(hour_angle_rad)
        cos_zenith = np.clip(cos_zenith, -1.0, 1.0)
        zenith_rad = np.arccos(cos_zenith)
        zenith_deg = np.degrees(zenith_rad)

        # Solar elevation angle (degrees)
        elevation_deg = 90.0 - zenith_deg

        # Solar azimuth angle (degrees from North)
        cos_azimuth = (np.sin(declination) * np.cos(lat_rad) - np.cos(declination) * np.sin(lat_rad) * np.cos(hour_angle_rad)) / np.sin(zenith_rad)
        cos_azimuth = np.clip(cos_azimuth, -1.0, 1.0)
        azimuth_rad = np.arccos(cos_azimuth)
        azimuth_deg = np.degrees(azimuth_rad)
        # Adjust for afternoon
        azimuth_deg = np.where(hour_angle_deg > 0, 360.0 - azimuth_deg, azimuth_deg)

        return pd.DataFrame({
            "solar_zenith_deg": zenith_deg,
            "solar_elevation_deg": elevation_deg,
            "solar_azimuth_deg": azimuth_deg,
            "cos_zenith": np.maximum(0.0, cos_zenith),
        }, index=dt.index if hasattr(dt, "index") else None)

    def compute_clear_sky_ghi(self, solar_pos: pd.DataFrame) -> pd.Series:
        """
        Estimate Clear-Sky Global Horizontal Irradiance (GHI) using Haurwitz model.
        G_clear = 1098 * cos(theta_z) * exp(-0.057 / cos(theta_z)) when cos(theta_z) > 0.
        """
        cos_z = solar_pos["cos_zenith"]
        clear_sky = np.zeros(len(cos_z))
        day_mask = cos_z > 0.05
        clear_sky[day_mask] = 1098.0 * cos_z[day_mask] * np.exp(-0.057 / cos_z[day_mask])
        return pd.Series(np.maximum(0.0, clear_sky), index=solar_pos.index, name="clear_sky_ghi")

    def estimate_poa_from_ghi(
        self,
        ghi: pd.Series,
        solar_pos: pd.DataFrame
    ) -> pd.Series:
        """
        Transposition model: Transpose Global Horizontal Irradiance (GHI) to Plane-of-Array (POA) irradiance.
        Uses isotropic sky diffuse model (Liu & Jordan) with ground reflection.
        """
        tilt_rad = math.radians(self.tilt_deg)
        cos_z = solar_pos["cos_zenith"].values
        elev_deg = solar_pos["solar_elevation_deg"].values
        az_deg = solar_pos["solar_azimuth_deg"].values

        # Angle of incidence (AOI) on tilted plane
        panel_az_rad = math.radians(self.azimuth_deg)
        sol_az_rad = np.radians(az_deg)
        zen_rad = np.radians(solar_pos["solar_zenith_deg"].values)

        cos_aoi = (
            np.cos(zen_rad) * np.cos(tilt_rad)
            + np.sin(zen_rad) * np.sin(tilt_rad) * np.cos(sol_az_rad - panel_az_rad)
        )
        cos_aoi = np.maximum(0.0, cos_aoi)

        # Beam ratio Rb = cos(aoi) / cos(zenith)
        safe_cos_z = np.maximum(cos_z, 0.087) # avoid division by near-zero at sunrise/sunset
        rb = np.where(cos_z > 0.05, cos_aoi / safe_cos_z, 0.0)

        # Simple diffuse fraction decomposition (Erbs correlation estimate)
        # kt = GHI / (G_0 * cos_z)
        g0 = 1361.0
        kt = np.where(safe_cos_z > 0.1, ghi.values / (g0 * safe_cos_z), 0.0)
        kt = np.clip(kt, 0.0, 1.0)
        # Diffuse fraction kd = DHI / GHI
        kd = np.where(
            kt <= 0.22,
            1.0 - 0.09 * kt,
            np.where(
                kt <= 0.80,
                0.9511 - 0.1604 * kt + 4.388 * (kt**2) - 16.638 * (kt**3) + 12.336 * (kt**4),
                0.165
            )
        )
        kd = np.clip(kd, 0.0, 1.0)

        dhi = ghi.values * kd
        dni_cos = ghi.values * (1.0 - kd)

        # POA components:
        # 1. Beam on tilted surface
        poa_beam = np.maximum(0.0, dni_cos * rb)
        # 2. Diffuse on tilted surface (isotropic)
        poa_diffuse = dhi * (1.0 + math.cos(tilt_rad)) / 2.0
        # 3. Ground reflected albedo
        poa_ground = ghi.values * self.ground_albedo * (1.0 - math.cos(tilt_rad)) / 2.0

        poa_total = poa_beam + poa_diffuse + poa_ground
        # Nighttime zero clamping
        poa_total = np.where(elev_deg <= 0.0, 0.0, poa_total)
        return pd.Series(np.maximum(0.0, poa_total), index=ghi.index, name="plane_of_array_irradiance")
