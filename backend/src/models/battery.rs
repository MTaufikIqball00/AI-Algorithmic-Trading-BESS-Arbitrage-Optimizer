use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatteryConfig {
    pub asset_id: String,
    pub name: String,
    pub capacity_mwh: f64,
    pub power_mw: f64,
    pub soc_min: f64,
    pub soc_max: f64,
    pub eta_charge: f64,
    pub eta_discharge: f64,
    pub cell_replacement_cost_per_mwh: f64,
    pub cycle_life_nominal: f64,
    pub transaction_fee_per_mwh: f64,
    pub ramp_rate_mw_per_min: f64,
}

impl Default for BatteryConfig {
    fn default() -> Self {
        Self {
            asset_id: "BESS_CAISO_1".to_string(),
            name: "CAISO Utility-Scale 100MWh/50MW LFP BESS".to_string(),
            capacity_mwh: 100.0,
            power_mw: 50.0,
            soc_min: 0.05,
            soc_max: 0.95,
            eta_charge: 0.94,
            eta_discharge: 0.94,
            cell_replacement_cost_per_mwh: 120_000.0,
            cycle_life_nominal: 5000.0,
            transaction_fee_per_mwh: 0.50,
            ramp_rate_mw_per_min: 25.0,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BatteryState {
    pub soc: f64,
    pub active_power_mw: f64, // positive = discharge to grid, negative = charge from grid
    pub temperature_c: f64,
    pub state_of_health_pct: f64,
    pub total_throughput_mwh: f64,
    pub equivalent_full_cycles: f64,
    pub cumulative_degradation_cost: f64,
}
