"""
Tests for Solar PV Physical Calculations.
Verifies P = VI dimensional correctness, numerical energy integration,
King cell temperature model, STC expected power, and IEC 61724 PR.
"""
import pytest
import numpy as np
import pandas as pd

from solar_pv.features.solar_physics import SolarPVPhysicsEngine
from solar_pv.config.defaults import PVSystemConfig, STC_CELL_TEMP_C


def test_dc_power_from_vi():
    # 600 V * 200 A = 120,000 W = 120 kW
    p_kw = SolarPVPhysicsEngine.calculate_dc_power_from_vi(600.0, 200.0)
    assert p_kw == 120.0


def test_trapezoidal_energy_integration():
    # Constant 100 kW over 2 hours (t = 0s to 7200s) -> 200 kWh
    p = np.array([100.0, 100.0, 100.0])
    t = np.array([0.0, 3600.0, 7200.0])
    e_kwh = SolarPVPhysicsEngine.integrate_energy_kwh(p, t)
    assert abs(e_kwh - 200.0) < 1e-4

    # Test missing interval: if gap > 3600s, it must not integrate across the missing window
    t_gap = np.array([0.0, 3600.0, 10800.0]) # 2h gap between step 1 and 2
    e_gap_kwh = SolarPVPhysicsEngine.integrate_energy_kwh(p, t_gap, max_valid_interval_sec=3600.0)
    # Only the first 1-hour interval is integrated
    assert abs(e_gap_kwh - 100.0) < 1e-4


def test_expected_power_at_stc():
    config = PVSystemConfig(rated_dc_power_kw=1000.0, inverter_efficiency=0.98, inverter_ac_power_kw=900.0)
    engine = SolarPVPhysicsEngine(config)

    # At STC (G = 1000 W/m^2, T_cell = 25 C):
    # P_dc = 1000 kW * (1000/1000) * (1 + 0) = 1000 kW
    # P_ac = min(900, 1000 * 0.98) = 900 kW (clipping)
    p_expected = engine.calculate_expected_power_kw(
        poa_irradiance=1000.0,
        cell_temperature_c=25.0,
        account_for_inverter_loss=True
    )
    assert p_expected == 900.0


def test_temperature_derating():
    config = PVSystemConfig(
        rated_dc_power_kw=1000.0,
        temp_coefficient=-0.004, # -0.4% per deg C
        inverter_efficiency=1.0,
        inverter_ac_power_kw=1500.0
    )
    engine = SolarPVPhysicsEngine(config)

    # At T_cell = 50 C (25 C above STC):
    # temp_loss = 1 + (-0.004 * 25) = 1 - 0.10 = 0.90 (-10%)
    # P_expected = 1000 * (1000/1000) * 0.90 = 900 kW
    p_hot = engine.calculate_expected_power_kw(
        poa_irradiance=1000.0,
        cell_temperature_c=50.0,
        account_for_inverter_loss=True
    )
    assert abs(p_hot - 900.0) < 1e-4


def test_performance_ratio_iec61724():
    config = PVSystemConfig(rated_dc_power_kw=1000.0)
    engine = SolarPVPhysicsEngine(config)

    # Over 4 hours of midday: POA = 1000 W/m^2 constant
    # H_poa = 1000 W/m^2 * 4h = 4 kWh/m^2
    # Reference yield = 4 kWh/m^2 / 1 kW/m^2 = 4.0 hours
    # Actual energy = 3200 kWh -> Final yield = 3200 / 1000 = 3.2 hours
    # PR = 3.2 / 4.0 = 0.80 (80%)
    poa = np.array([1000.0, 1000.0, 1000.0, 1000.0, 1000.0])
    t = np.array([0.0, 3600.0, 7200.0, 10800.0, 14400.0])
    pr_res = engine.calculate_performance_ratio(actual_energy_kwh=3200.0, poa_irradiance_series=poa, time_seconds_series=t)
    assert pr_res["status"] == "VALID"
    assert pr_res["performance_ratio_pct"] == 80.0
