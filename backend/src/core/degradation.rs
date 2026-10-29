#[derive(Debug, Clone)]
pub struct DegradationModel {
    pub cell_replacement_cost_per_mwh: f64,
    pub nominal_cycle_life: f64,
    pub capacity_mwh: f64,
}

impl DegradationModel {
    pub fn new(cell_cost: f64, cycle_life: f64, capacity: f64) -> Self {
        Self {
            cell_replacement_cost_per_mwh: cell_cost,
            nominal_cycle_life: cycle_life,
            capacity_mwh: capacity,
        }
    }

    /// Calculate degradation cost in USD for a given throughput (MWh)
    pub fn calculate_cost(&self, throughput_mwh: f64) -> f64 {
        let rate_per_mwh = self.cell_replacement_cost_per_mwh / (2.0 * self.nominal_cycle_life);
        throughput_mwh * rate_per_mwh
    }

    /// Calculate equivalent full cycles (EFC)
    pub fn calculate_efc(&self, total_throughput_mwh: f64) -> f64 {
        if self.capacity_mwh > 0.0 {
            total_throughput_mwh / (2.0 * self.capacity_mwh)
        } else {
            0.0
        }
    }

    /// Calculate State of Health percentage remaining (100% to 80% EOL)
    pub fn calculate_soh(&self, total_throughput_mwh: f64) -> f64 {
        let efc = self.calculate_efc(total_throughput_mwh);
        let lost_fraction = (efc / self.nominal_cycle_life) * 0.20;
        ((1.0 - lost_fraction).clamp(0.0, 1.0) * 100.0 * 100.0).round() / 100.0
    }
}
