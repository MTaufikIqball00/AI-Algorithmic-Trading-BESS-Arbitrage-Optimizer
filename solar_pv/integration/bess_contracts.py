"""
Integration Contracts and Typed Interfaces for BESS Optimization Coupling.
Defines typed schemas for PV production forecasts, asset availability,
net site load calculations, and hybrid solar-plus-storage dispatch constraints.
"""
from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class PVSourceType(str, Enum):
    REAL_HISTORICAL = "REAL_HISTORICAL"
    SYNTHETIC_SIMULATED = "SYNTHETIC_SIMULATED"


class PVDataQualityStatus(str, Enum):
    VERIFIED = "VERIFIED"
    LIMITED = "LIMITED"
    INTERPOLATED = "INTERPOLATED"
    SUSPECT = "SUSPECT"
    SYNTHETIC = "SYNTHETIC"


class PredictionInterval(BaseModel):
    lower_80: float = Field(..., description="80% lower prediction bound in kW")
    upper_80: float = Field(..., description="80% upper prediction bound in kW")
    lower_95: float = Field(..., description="95% lower prediction bound in kW")
    upper_95: float = Field(..., description="95% upper prediction bound in kW")


class PVForecastPoint(BaseModel):
    asset_id: str = Field(..., description="Identifier of the solar array or plant")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp of forecast point")
    forecast_horizon_minutes: int = Field(60, description="Step duration in minutes")
    predicted_power_kw: float = Field(..., ge=0.0, description="Predicted active generation in kW")
    predicted_power_mw: float = Field(..., ge=0.0, description="Predicted active generation in MW")
    predicted_energy_kwh: float = Field(..., ge=0.0, description="Predicted energy yield in kWh")
    predicted_energy_mwh: float = Field(..., ge=0.0, description="Predicted energy yield in MWh")
    prediction_interval: PredictionInterval
    model_version: str = Field("solar_pv_xgb_v1.0", description="Forecasting model version")
    data_quality: PVDataQualityStatus = Field(PVDataQualityStatus.VERIFIED, description="Input data quality status")
    source_type: PVSourceType = Field(PVSourceType.REAL_HISTORICAL, description="Data provenance")
    availability_factor: float = Field(1.0, ge=0.0, le=1.0, description="Asset availability fraction (1.0 = 100%)")
    performance_ratio_expected: Optional[float] = Field(None, description="Expected temperature-corrected PR")


class PVForecastPayload(BaseModel):
    site_id: str = Field(..., description="BESS + PV co-located site identifier")
    generated_at: str = Field(..., description="ISO 8601 generation timestamp")
    horizon_hours: int = Field(24, ge=1, le=168, description="Total forecast horizon in hours")
    total_forecast_energy_mwh: float = Field(..., ge=0.0, description="Integrated forecast energy over horizon")
    peak_forecast_power_mw: float = Field(..., ge=0.0, description="Peak forecast solar power over horizon")
    points: List[PVForecastPoint] = Field(..., description="Chronological series of forecast points")


class BESSCoLocatedDispatchConstraint(BaseModel):
    site_interconnection_limit_mw: float = Field(100.0, description="Maximum net power flow through POI to grid (MW)")
    bess_max_charge_mw: float = Field(50.0, description="Maximum BESS charging power (MW)")
    bess_max_discharge_mw: float = Field(50.0, description="Maximum BESS discharging power (MW)")
    bess_capacity_mwh: float = Field(100.0, description="Nominal BESS storage capacity (MWh)")
    soc_min: float = Field(0.05, ge=0.0, le=0.5, description="Minimum state of charge boundary (fraction)")
    soc_max: float = Field(0.95, ge=0.5, le=1.0, description="Maximum state of charge boundary (fraction)")
    eta_charge: float = Field(0.94, ge=0.7, le=1.0, description="BESS charging conversion efficiency")
    allow_grid_charging: bool = Field(True, description="Whether battery can charge from grid or solar-only")
    solar_curtailment_penalty_per_mwh: float = Field(10.0, description="Penalty for wasting available solar")


class SolarCoupledDispatchDecision(BaseModel):
    timestamp: str
    solar_available_mw: float
    solar_to_load_mw: float
    solar_to_bess_charge_mw: float
    solar_to_grid_export_mw: float
    solar_curtailed_mw: float
    bess_grid_charge_mw: float
    bess_grid_discharge_mw: float
    net_grid_flow_mw: float # positive = export to grid, negative = import from grid
    resulting_soc: float
    constraint_violated: bool = False
