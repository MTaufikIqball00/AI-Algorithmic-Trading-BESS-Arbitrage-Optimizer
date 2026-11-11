"""
Solar PV and BESS Integration Adapter.
Implements energy-conserving dispatch coupling, zero-double-counting arithmetic,
interconnection constraint enforcement, and typed payload formatting for the BESS optimizer.
"""
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
from datetime import datetime

from .bess_contracts import (
    PVForecastPoint,
    PVForecastPayload,
    PredictionInterval,
    PVDataQualityStatus,
    PVSourceType,
    BESSCoLocatedDispatchConstraint,
    SolarCoupledDispatchDecision
)


class BESSIntegrationAdapter:
    """
    Connects Solar PV analytical outputs to the existing BESS optimization system.
    """

    @staticmethod
    def format_forecast_payload(
        predictions: List[Dict[str, Any]],
        site_id: str = "hybrid_site_sp15",
        source_type: PVSourceType = PVSourceType.REAL_HISTORICAL,
        data_quality: PVDataQualityStatus = PVDataQualityStatus.VERIFIED,
        availability_factor: float = 1.0
    ) -> PVForecastPayload:
        """
        Convert prediction dictionary list to typed, validated PVForecastPayload.
        """
        points: List[PVForecastPoint] = []
        total_energy_kwh = 0.0
        peak_power_kw = 0.0

        for p in predictions:
            p_kw = max(0.0, float(p.get("predicted_power_kw", 0.0)))
            p_mw = p_kw / 1000.0
            e_kwh = max(0.0, float(p.get("predicted_energy_kwh", p_kw * 1.0)))
            e_mwh = e_kwh / 1000.0

            total_energy_kwh += e_kwh
            if p_kw > peak_power_kw:
                peak_power_kw = p_kw

            interval = PredictionInterval(
                lower_80=max(0.0, float(p.get("lower_bound_80", p_kw * 0.85))),
                upper_80=float(p.get("upper_bound_80", p_kw * 1.15)),
                lower_95=max(0.0, float(p.get("lower_bound_95", p_kw * 0.70))),
                upper_95=float(p.get("upper_bound_95", p_kw * 1.30))
            )

            interval_min = int(p.get("interval_minutes", 60))
            point = PVForecastPoint(
                asset_id=p.get("panel_id", site_id),
                timestamp=str(p["timestamp"]),
                forecast_horizon_minutes=interval_min,
                predicted_power_kw=round(p_kw, 2),
                predicted_power_mw=round(p_mw, 4),
                predicted_energy_kwh=round(e_kwh, 2),
                predicted_energy_mwh=round(e_mwh, 4),
                prediction_interval=interval,
                model_version=str(p.get("model_version", "solar_pv_xgb_v1.0")),
                data_quality=data_quality,
                source_type=source_type,
                availability_factor=availability_factor
            )
            points.append(point)

        total_minutes = sum(pt.forecast_horizon_minutes for pt in points)
        horizon_hours = max(1, int(round(total_minutes / 60.0))) if points else 0

        return PVForecastPayload(
            site_id=site_id,
            generated_at=datetime.utcnow().isoformat() + "Z",
            horizon_hours=horizon_hours,
            total_forecast_energy_mwh=round(total_energy_kwh / 1000.0, 3),
            peak_forecast_power_mw=round(peak_power_kw / 1000.0, 3),
            points=points
        )

    @staticmethod
    def dispatch_coupled_solar_step(
        solar_power_mw: float,
        site_load_mw: float,
        current_soc: float,
        requested_bess_power_mw: float, # positive = discharge, negative = charge
        constraints: BESSCoLocatedDispatchConstraint,
        dt_hours: float = 1.0,
        timestamp: str = ""
    ) -> SolarCoupledDispatchDecision:
        """
        Execute a physically coupled solar-plus-storage dispatch step.
        Guarantees zero double counting and absolute conservation of energy.
        """
        p_solar = max(0.0, float(solar_power_mw))
        p_load = max(0.0, float(site_load_mw))
        soc = float(current_soc)
        constraint_violated = False

        # 1. Supply on-site load with available solar generation first
        solar_to_load = min(p_solar, p_load)
        surplus_solar = p_solar - solar_to_load

        # 2. Determine BESS charging capacity headroom:
        # Max power battery can accept before reaching soc_max:
        # (soc_max - soc) * E_nom / (eta_charge * dt)
        if constraints.eta_charge > 0:
            max_charge_power_by_soc = max(
                0.0,
                (constraints.soc_max - soc) * constraints.bess_capacity_mwh / (constraints.eta_charge * dt_hours)
            )
        else:
            max_charge_power_by_soc = 0.0

        max_allowed_charge_power = min(constraints.bess_max_charge_mw, max_charge_power_by_soc)

        # 3. Determine BESS discharging capacity headroom:
        # Max power battery can deliver before reaching soc_min:
        # (soc - soc_min) * E_nom * eta_discharge / dt
        max_deliver_power_by_soc = max(
            0.0,
            (soc - constraints.soc_min) * constraints.bess_capacity_mwh * 0.94 / dt_hours
        )
        max_allowed_discharge_power = min(constraints.bess_max_discharge_mw, max_deliver_power_by_soc)

        # 4. Allocate surplus solar to BESS charging
        # If requested_power is negative (charge) or surplus solar is available
        solar_to_bess = min(surplus_solar, max_allowed_charge_power)
        remaining_solar = surplus_solar - solar_to_bess

        # Check if requested charging exceeds solar and grid charging is enabled
        bess_grid_charge = 0.0
        bess_grid_discharge = 0.0

        if requested_bess_power_mw < 0.0:
            req_charge = abs(requested_bess_power_mw)
            # Charging already partly satisfied by solar
            remaining_req_charge = max(0.0, req_charge - solar_to_bess)
            if constraints.allow_grid_charging:
                bess_grid_charge = min(remaining_req_charge, max(0.0, max_allowed_charge_power - solar_to_bess))
        elif requested_bess_power_mw > 0.0:
            # Requested discharge
            bess_grid_discharge = min(requested_bess_power_mw, max_allowed_discharge_power)

        # Total battery energy absorbed and delivered
        total_battery_charge_mw = solar_to_bess + bess_grid_charge
        energy_stored_mwh = total_battery_charge_mw * dt_hours * constraints.eta_charge
        energy_depleted_mwh = (bess_grid_discharge * dt_hours) / 0.94 if bess_grid_discharge > 0 else 0.0

        # Update SoC
        delta_soc = (energy_stored_mwh - energy_depleted_mwh) / constraints.bess_capacity_mwh
        new_soc = float(np.clip(soc + delta_soc, constraints.soc_min, constraints.soc_max))

        # 5. Grid Export and Curtailment:
        # Net grid flow = Solar exported to grid + BESS discharged - (BESS grid charge + Unmet load)
        unmet_load = max(0.0, p_load - solar_to_load)
        
        # Solar to grid export
        max_export_room = max(0.0, constraints.site_interconnection_limit_mw - bess_grid_discharge)
        solar_to_grid = min(remaining_solar, max_export_room)
        solar_curtailed = remaining_solar - solar_to_grid

        net_grid_flow = (solar_to_grid + bess_grid_discharge) - (bess_grid_charge + unmet_load)

        # Check POI interconnection limit violation
        if abs(net_grid_flow) > constraints.site_interconnection_limit_mw + 1e-4:
            constraint_violated = True

        return SolarCoupledDispatchDecision(
            timestamp=timestamp,
            solar_available_mw=round(p_solar, 4),
            solar_to_load_mw=round(solar_to_load, 4),
            solar_to_bess_charge_mw=round(solar_to_bess, 4),
            solar_to_grid_export_mw=round(solar_to_grid, 4),
            solar_curtailed_mw=round(solar_curtailed, 4),
            bess_grid_charge_mw=round(bess_grid_charge, 4),
            bess_grid_discharge_mw=round(bess_grid_discharge, 4),
            net_grid_flow_mw=round(net_grid_flow, 4),
            resulting_soc=round(new_soc, 4),
            constraint_violated=constraint_violated
        )
