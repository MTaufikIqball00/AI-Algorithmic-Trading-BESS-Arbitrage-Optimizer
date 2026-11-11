"""Configuration defaults and physical constants for Solar PV module."""
from dataclasses import dataclass, field
from typing import Dict, Any

# Standard Test Conditions (STC)
STC_IRRADIANCE_W_PER_M2 = 1000.0  # W/m^2
STC_CELL_TEMP_C = 25.0             # deg C
STC_AIR_MASS = 1.5

# Nominal Operating Cell Temperature (NOCT) defaults
DEFAULT_NOCT_C = 45.0
DEFAULT_TEMP_COEFF_PMP = -0.0038  # -0.38%/deg C for typical monocrystalline Si

# Physical limits for validation
MIN_IRRADIANCE = 0.0
MAX_IRRADIANCE = 1500.0            # W/m^2 (accounts for edge-of-cloud concentration)
MIN_AMBIENT_TEMP_C = -40.0
MAX_AMBIENT_TEMP_C = 60.0
MIN_CELL_TEMP_C = -40.0
MAX_CELL_TEMP_C = 95.0
MIN_WIND_SPEED_M_S = 0.0
MAX_WIND_SPEED_M_S = 55.0
MIN_RELATIVE_HUMIDITY = 0.0
MAX_RELATIVE_HUMIDITY = 100.0

@dataclass
class PVSystemConfig:
    system_id: str = "pv_system_001"
    system_name: str = "Default Monocrystalline PV Array"
    rated_dc_power_kw: float = 1000.0       # 1 MWp array
    inverter_ac_power_kw: float = 850.0     # 850 kW AC inverter capacity
    inverter_efficiency: float = 0.975      # 97.5% nominal inverter efficiency
    temp_coefficient: float = DEFAULT_TEMP_COEFF_PMP  # 1/deg C
    panel_tilt_deg: float = 25.0            # Array tilt angle from horizontal
    panel_azimuth_deg: float = 180.0        # Array azimuth (180 = South in Northern Hemisphere)
    latitude: float = 34.05                 # Site latitude (e.g. Southern California / SP15)
    longitude: float = -117.20              # Site longitude
    altitude_m: float = 300.0               # Altitude above sea level in meters
    commissioning_date: str = "2020-01-01"
