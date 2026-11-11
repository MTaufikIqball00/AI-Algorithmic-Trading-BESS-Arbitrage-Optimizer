"""
Solar PV Physical Performance Modeling Engine.
Implements physically grounded equations for electrical power, numerical energy integration,
temperature-corrected expected PV power (STC benchmark), and Performance Ratio (PR).
Strictly enforces dimensional consistency and input validity.
"""
import math
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, Union

from ..config.defaults import (
    PVSystemConfig,
    STC_IRRADIANCE_W_PER_M2,
    STC_CELL_TEMP_C,
    DEFAULT_TEMP_COEFF_PMP,
    DEFAULT_NOCT_C
)


class SolarPVPhysicsEngine:
    """
    Executes first-principles photovoltaic physics calculations.
    """

    def __init__(self, config: Optional[PVSystemConfig] = None):
        self.config = config or PVSystemConfig()

    @staticmethod
    def calculate_dc_power_from_vi(
        voltage_v: Union[float, np.ndarray, pd.Series],
        current_a: Union[float, np.ndarray, pd.Series]
    ) -> Union[float, np.ndarray, pd.Series]:
        """
        Calculate DC Electrical Power: P = V * I.
        Returns power in kiloWatts (kW).
        Prerequisite: Voltage (V) and Current (A) must be strictly synchronized and compatible.
        """
        # P (kW) = V (V) * I (A) / 1000.0
        p_kw = (voltage_v * current_a) / 1000.0
        if isinstance(p_kw, (pd.Series, np.ndarray)):
            return np.maximum(0.0, p_kw)
        return max(0.0, float(p_kw))

    @staticmethod
    def integrate_energy_kwh(
        power_kw: Union[np.ndarray, pd.Series],
        time_seconds: Union[np.ndarray, pd.Series],
        max_valid_interval_sec: float = 3600.0
    ) -> float:
        """
        Energy is the time integral of active power: E = \\int P(t) dt.
        Uses trapezoidal numerical integration.
        Detects missing intervals: if dt > max_valid_interval_sec, does not interpolate blindly across the gap.
        Returns total energy in kiloWatt-hours (kWh).
        """
        p = np.asarray(power_kw, dtype=np.float64)
        t = np.asarray(time_seconds, dtype=np.float64)

        if len(p) < 2 or len(t) < 2:
            return 0.0

        dt = np.diff(t)
        # Mask out gaps exceeding max valid interval
        valid_mask = (dt > 0) & (dt <= max_valid_interval_sec)
        
        # Trapezoidal rule for each valid interval: 0.5 * (P_i + P_{i+1}) * dt / 3600
        p_avg = 0.5 * (p[:-1] + p[1:])
        energy_intervals_kwh = np.where(valid_mask, (p_avg * dt) / 3600.0, 0.0)
        
        return float(np.sum(np.maximum(0.0, energy_intervals_kwh)))

    def estimate_cell_temperature(
        self,
        ambient_temp_c: Union[float, np.ndarray, pd.Series],
        poa_irradiance: Union[float, np.ndarray, pd.Series],
        wind_speed_m_s: Optional[Union[float, np.ndarray, pd.Series]] = None
    ) -> Union[float, np.ndarray, pd.Series]:
        """
        Estimate photovoltaic cell operating temperature T_cell.
        If wind speed is provided: uses King / Sandia open-rack thermal model:
            T_cell = T_amb + G_poa * exp(-3.56 - 0.075 * v_wind)
        Otherwise uses standard NOCT formula:
            T_cell = T_amb + (NOCT - 20) * (G_poa / 800.0)
        """
        if wind_speed_m_s is not None:
            # Sandia thermal model
            thermal_rise = poa_irradiance * np.exp(-3.56 - 0.075 * wind_speed_m_s)
            return ambient_temp_c + thermal_rise
        else:
            # NOCT model
            return ambient_temp_c + ((DEFAULT_NOCT_C - 20.0) / 800.0) * poa_irradiance

    def calculate_expected_power_kw(
        self,
        poa_irradiance: Union[float, np.ndarray, pd.Series],
        cell_temperature_c: Optional[Union[float, np.ndarray, pd.Series]] = None,
        ambient_temperature_c: Optional[Union[float, np.ndarray, pd.Series]] = None,
        wind_speed_m_s: Optional[Union[float, np.ndarray, pd.Series]] = None,
        account_for_inverter_loss: bool = True
    ) -> Union[float, np.ndarray, pd.Series]:
        """
        Physically grounded expected PV power production:
            P_expected = P_STC * (G_POA / G_STC) * [1 + gamma * (T_cell - T_STC)]
        Parameters:
            poa_irradiance: Plane-of-array irradiance in W/m^2
            cell_temperature_c: Measured module/cell temperature in deg C
            ambient_temperature_c: Used to model cell temp if cell_temperature_c is None
        Returns:
            P_expected in kW
        """
        g_poa = np.asarray(poa_irradiance, dtype=np.float64) if isinstance(poa_irradiance, (list, np.ndarray, pd.Series)) else float(poa_irradiance)

        if cell_temperature_c is not None:
            t_cell = np.asarray(cell_temperature_c, dtype=np.float64) if isinstance(cell_temperature_c, (list, np.ndarray, pd.Series)) else float(cell_temperature_c)
        elif ambient_temperature_c is not None:
            t_cell = self.estimate_cell_temperature(ambient_temperature_c, poa_irradiance, wind_speed_m_s)
        else:
            # Fallback to STC temperature (disclosing unadjusted baseline limitation)
            t_cell = STC_CELL_TEMP_C

        # Temperature loss factor: 1 + gamma * (T_cell - 25.0)
        temp_factor = 1.0 + self.config.temp_coefficient * (t_cell - STC_CELL_TEMP_C)
        temp_factor = np.clip(temp_factor, 0.50, 1.30)

        # Expected DC power
        p_dc_expected = self.config.rated_dc_power_kw * (g_poa / STC_IRRADIANCE_W_PER_M2) * temp_factor

        if account_for_inverter_loss:
            # Inverter AC conversion and clipping
            p_ac_expected = p_dc_expected * self.config.inverter_efficiency
            p_ac_expected = np.clip(p_ac_expected, 0.0, self.config.inverter_ac_power_kw)
            return p_ac_expected

        return np.maximum(0.0, p_dc_expected)

    def calculate_performance_ratio(
        self,
        actual_energy_kwh: float,
        poa_irradiance_series: Union[np.ndarray, pd.Series],
        time_seconds_series: Union[np.ndarray, pd.Series]
    ) -> Dict[str, Any]:
        """
        Calculate IEC 61724 Standard Performance Ratio (PR):
            PR = Y_f / Y_r = (E_actual / P_STC) / (H_POA / G_STC)
        where:
            Y_f: Final Yield (kWh / kWp = equivalent full hours)
            Y_r: Reference Yield (kWh / kWp = H_POA / 1000 W/m^2)
            H_POA: Cumulative incident irradiation on tilted array in kWh/m^2
        """
        if self.config.rated_dc_power_kw <= 0.0:
            return {"error": "Invalid rated DC power <= 0", "performance_ratio": None}

        # Integrate irradiation H_POA (kWh/m^2)
        poa = np.asarray(poa_irradiance_series, dtype=np.float64)
        t = np.asarray(time_seconds_series, dtype=np.float64)

        if len(poa) < 2:
            return {"error": "Insufficient time-series points", "performance_ratio": None}

        dt_hours = np.diff(t) / 3600.0
        valid_dt = (dt_hours > 0) & (dt_hours <= 1.0)
        poa_avg = 0.5 * (poa[:-1] + poa[1:])
        # H_POA in kWh/m^2 = sum(poa_avg [W/m^2] * dt [h]) / 1000
        h_poa_kwh_per_m2 = float(np.sum(np.where(valid_dt, (poa_avg * dt_hours) / 1000.0, 0.0)))

        if h_poa_kwh_per_m2 <= 0.001:
            return {
                "status": "INSUFFICIENT_SUNLIGHT",
                "performance_ratio": None,
                "actual_energy_kwh": actual_energy_kwh,
                "reference_yield_hours": 0.0,
                "final_yield_hours": 0.0,
                "note": "Reference irradiation near zero (nighttime or heavy shadow)."
            }

        # Final yield (hours)
        final_yield_h = actual_energy_kwh / self.config.rated_dc_power_kw
        # Reference yield (hours)
        reference_yield_h = h_poa_kwh_per_m2 / (STC_IRRADIANCE_W_PER_M2 / 1000.0)

        pr = final_yield_h / reference_yield_h if reference_yield_h > 0 else 0.0
        pr_pct = round(pr * 100.0, 2)

        return {
            "status": "VALID",
            "performance_ratio": pr,
            "performance_ratio_pct": pr_pct,
            "actual_energy_kwh": round(actual_energy_kwh, 2),
            "final_yield_hours": round(final_yield_h, 2),
            "reference_yield_hours": round(reference_yield_h, 2),
            "cumulative_poa_irradiation_kwh_m2": round(h_poa_kwh_per_m2, 3),
            "rated_dc_capacity_kw": self.config.rated_dc_power_kw,
            "standard": "IEC 61724"
        }
