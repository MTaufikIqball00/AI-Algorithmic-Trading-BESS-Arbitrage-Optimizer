"""
Tests for Predictive Maintenance Advisor and BESS Integration Adapter.
Verifies condition prioritization and energy conservation in coupled dispatch steps.
"""
import pytest
from pydantic import ValidationError

from solar_pv.maintenance.risk_scoring import PVRiskScorer
from solar_pv.maintenance.recommendations import PVMaintenanceAdvisor, MaintenancePriority
from solar_pv.anomaly_detection.evidence import (
    AnomalyEvent, AnomalyClassification, AnomalySeverity, EvidenceBundle
)
from solar_pv.integration.bess_contracts import (
    PVForecastPayload, PVForecastPoint, PredictionInterval,
    BESSCoLocatedDispatchConstraint, SolarCoupledDispatchDecision
)
from solar_pv.integration.adapters import BESSIntegrationAdapter


def test_maintenance_advisor_critical_hardware_recommendation():
    advisor = PVMaintenanceAdvisor()

    # Create dummy critical inverter trip event
    bundle = EvidenceBundle(
        irradiance_normalized_ratio=0.0,
        is_weather_explained=False,
        cloud_cover=0.0,
        irradiance_w_per_m2=900.0,
        voltage_v=600.0,
        current_a=0.0,
        inverter_status="FAULT_TRIPPED",
        sensor_status="NORMAL",
        days_since_cleaning=None,
        cumulative_rain_mm=None,
        is_stuck_sensor=False,
        evidence_notes=["Inverter status FAULT_TRIPPED under 900 W/m^2 irradiance."]
    )
    event = AnomalyEvent(
        asset_id="pv_site_01",
        start_time="2024-06-01T12:00:00Z",
        end_time="2024-06-01T15:00:00Z",
        actual_power_kw=0.0,
        expected_power_kw=850.0,
        residual_kw=-850.0,
        classification=AnomalyClassification.POTENTIAL_EQUIPMENT_FAULT,
        severity=AnomalySeverity.CRITICAL,
        confidence=0.95,
        evidence=bundle,
        model_version="solar_v1.0",
        data_quality="HARDWARE_ANOMALY"
    )

    recs = advisor.generate_recommendations("pv_site_01", [event])
    assert len(recs) > 0
    top_rec = recs[0]
    assert top_rec.priority == MaintenancePriority.CRITICAL
    assert "inverter" in top_rec.recommended_inspection.lower()


def test_bess_forecast_payload_contract_validation():
    interval = PredictionInterval(lower_80=80.0, upper_80=120.0, lower_95=70.0, upper_95=130.0)
    point = PVForecastPoint(
        asset_id="pv_array_01",
        timestamp="2024-06-01T12:00:00Z",
        forecast_horizon_minutes=60,
        predicted_power_kw=100.0,
        predicted_power_mw=0.100,
        predicted_energy_kwh=100.0,
        predicted_energy_mwh=0.100,
        prediction_interval=interval
    )
    payload = PVForecastPayload(
        site_id="site_alpha",
        generated_at="2024-06-01T11:00:00Z",
        horizon_hours=1,
        total_forecast_energy_mwh=0.100,
        peak_forecast_power_mw=0.100,
        points=[point]
    )
    assert payload.horizon_hours == 1
    assert payload.points[0].predicted_power_mw == 0.100


def test_bess_coupled_dispatch_energy_conservation():
    constraints = BESSCoLocatedDispatchConstraint(
        site_interconnection_limit_mw=100.0,
        bess_max_charge_mw=50.0,
        bess_max_discharge_mw=50.0,
        bess_capacity_mwh=100.0,
        soc_min=0.05,
        soc_max=0.95,
        eta_charge=0.94
    )

    # Case A: Midday surplus solar (80 MW solar, 20 MW load, SoC = 0.50)
    decision = BESSIntegrationAdapter.dispatch_coupled_solar_step(
        solar_power_mw=80.0,
        site_load_mw=20.0,
        current_soc=0.50,
        requested_bess_power_mw=-40.0, # request 40 MW charge
        constraints=constraints,
        dt_hours=1.0,
        timestamp="2024-06-01T13:00:00Z"
    )

    # Conservation of Energy check:
    # solar_available = solar_to_load + solar_to_bess + solar_to_grid + solar_curtailed
    total_solar_used = (
        decision.solar_to_load_mw +
        decision.solar_to_bess_charge_mw +
        decision.solar_to_grid_export_mw +
        decision.solar_curtailed_mw
    )
    assert abs(total_solar_used - 80.0) < 1e-4

    # Solar to load should equal site load (20 MW)
    assert decision.solar_to_load_mw == 20.0
    # Surplus 60 MW, battery can accept min(50, headroom) -> charges 45 MW or requested 40 MW
    assert decision.solar_to_bess_charge_mw > 0.0
    # SoC should have increased
    assert decision.resulting_soc > 0.50
    # No constraint violation
    assert not decision.constraint_violated


def test_bess_coupled_dispatch_hard_soc_limit_enforcement():
    constraints = BESSCoLocatedDispatchConstraint(
        site_interconnection_limit_mw=100.0,
        bess_max_charge_mw=50.0,
        bess_capacity_mwh=100.0,
        soc_min=0.05,
        soc_max=0.95,
        eta_charge=0.94
    )

    # Battery already at maximum SoC (0.95)
    decision = BESSIntegrationAdapter.dispatch_coupled_solar_step(
        solar_power_mw=80.0,
        site_load_mw=10.0,
        current_soc=0.95, # at max SoC
        requested_bess_power_mw=-50.0, # requested charge
        constraints=constraints,
        dt_hours=1.0,
        timestamp="2024-06-01T13:00:00Z"
    )

    # Battery cannot accept charge when at soc_max
    assert decision.solar_to_bess_charge_mw == 0.0
    assert decision.bess_grid_charge_mw == 0.0
    assert decision.resulting_soc <= 0.95
