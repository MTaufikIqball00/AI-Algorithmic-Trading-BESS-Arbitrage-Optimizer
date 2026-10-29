use crate::models::battery::{BatteryConfig, BatteryState};

#[derive(Debug, Clone)]
pub struct StepExecutionResult {
    pub actual_power_mw: f64,
    pub energy_delivered_mwh: f64, // positive = to grid, negative = from grid
    pub gross_revenue: f64,
    pub charging_cost: f64,
    pub degradation_cost: f64,
    pub transaction_fee: f64,
    pub net_profit: f64,
    pub new_soc: f64,
    pub constraint_violated: bool,
}

#[derive(Debug, Clone)]
pub struct BatteryDigitalTwin {
    pub config: BatteryConfig,
    pub soc: f64,
    pub total_throughput_mwh: f64,
    pub cumulative_degradation_cost: f64,
    pub total_discharged_mwh: f64,
    pub total_charged_mwh: f64,
    pub constraint_violation_count: usize,
}

impl BatteryDigitalTwin {
    pub fn new(config: BatteryConfig, initial_soc: f64) -> Self {
        let clamped_soc = initial_soc.clamp(config.soc_min, config.soc_max);
        Self {
            config,
            soc: clamped_soc,
            total_throughput_mwh: 0.0,
            cumulative_degradation_cost: 0.0,
            total_discharged_mwh: 0.0,
            total_charged_mwh: 0.0,
            constraint_violation_count: 0,
        }
    }

    pub fn get_state(&self) -> BatteryState {
        // Equivalent Full Cycles = Throughput / (2 * Nominal Capacity)
        let efc = self.total_throughput_mwh / (2.0 * self.config.capacity_mwh);
        // SOH degradation: 80% EOL at nominal cycles
        let degradation_fraction = (efc / self.config.cycle_life_nominal) * 0.20;
        let soh = (1.0 - degradation_fraction).clamp(0.0, 1.0) * 100.0;

        BatteryState {
            soc: self.soc,
            active_power_mw: 0.0,
            temperature_c: 25.0,
            state_of_health_pct: (soh * 100.0).round() / 100.0,
            total_throughput_mwh: (self.total_throughput_mwh * 100.0).round() / 100.0,
            equivalent_full_cycles: (efc * 100.0).round() / 100.0,
            cumulative_degradation_cost: (self.cumulative_degradation_cost * 100.0).round() / 100.0,
        }
    }

    pub fn step(
        &mut self,
        requested_power_mw: f64,
        dt_hours: f64,
        price: f64,
    ) -> StepExecutionResult {
        let mut constraint_violated = false;
        let p_max = self.config.power_mw;

        // Check if requested power exceeds hardware inverter rating
        if requested_power_mw.abs() > p_max + 1e-4 {
            constraint_violated = true;
            self.constraint_violation_count += 1;
        }

        let clamped_req_power = requested_power_mw.clamp(-p_max, p_max);
        let mut actual_power_mw = 0.0;
        let mut gross_revenue = 0.0;
        let mut charging_cost = 0.0;
        let mut throughput = 0.0;

        if clamped_req_power > 0.0 {
            // DISCHARGING to grid
            // Max energy available above soc_min: (soc - soc_min) * E_nom
            // Inverter output to grid: energy_delivered = internal_energy * eta_discharge
            let max_deliverable_power = (self.soc - self.config.soc_min)
                * self.config.capacity_mwh
                * self.config.eta_discharge
                / dt_hours;

            actual_power_mw = clamped_req_power.min(max_deliverable_power.max(0.0));
            let energy_to_grid = actual_power_mw * dt_hours;
            let internal_energy_depleted = if self.config.eta_discharge > 0.0 {
                energy_to_grid / self.config.eta_discharge
            } else {
                0.0
            };

            self.soc -= internal_energy_depleted / self.config.capacity_mwh;
            gross_revenue = energy_to_grid * price;
            throughput = energy_to_grid;
            self.total_discharged_mwh += energy_to_grid;
        } else if clamped_req_power < 0.0 {
            // CHARGING from grid
            let req_charge_power = clamped_req_power.abs();
            // Max headroom below soc_max: (soc_max - soc) * E_nom
            // Grid draw allowed: req_power * eta_charge <= headroom
            let max_absorb_power = (self.config.soc_max - self.soc) * self.config.capacity_mwh
                / (self.config.eta_charge * dt_hours);

            actual_power_mw = -req_charge_power.min(max_absorb_power.max(0.0));
            let energy_from_grid = actual_power_mw.abs() * dt_hours;
            let internal_energy_stored = energy_from_grid * self.config.eta_charge;

            self.soc += internal_energy_stored / self.config.capacity_mwh;
            charging_cost = energy_from_grid * price;
            throughput = energy_from_grid;
            self.total_charged_mwh += energy_from_grid;
        }

        // Clamp SoC for numerical precision
        self.soc = self.soc.clamp(self.config.soc_min, self.config.soc_max);

        // Degradation model: Cost = replacement_cost / (2 * cycles * capacity) * throughput
        let deg_rate =
            self.config.cell_replacement_cost_per_mwh / (2.0 * self.config.cycle_life_nominal);
        let degradation_cost = throughput * deg_rate;
        let transaction_fee = throughput * self.config.transaction_fee_per_mwh;
        let net_profit = gross_revenue - charging_cost - degradation_cost - transaction_fee;

        self.total_throughput_mwh += throughput;
        self.cumulative_degradation_cost += degradation_cost;

        StepExecutionResult {
            actual_power_mw,
            energy_delivered_mwh: actual_power_mw * dt_hours,
            gross_revenue,
            charging_cost,
            degradation_cost,
            transaction_fee,
            net_profit,
            new_soc: self.soc,
            constraint_violated,
        }
    }
}
