use crate::models::market::MarketPoint;

pub struct ThresholdHeuristic {
    pub buy_pct: f64,
    pub sell_pct: f64,
}

impl ThresholdHeuristic {
    pub fn new(buy_pct: f64, sell_pct: f64) -> Self {
        Self { buy_pct, sell_pct }
    }

    /// Compute action using trailing rolling window of prices to guarantee ZERO FUTURE LEAKAGE
    pub fn decide(&self, current_idx: usize, dataset: &[MarketPoint], max_power_mw: f64) -> f64 {
        if current_idx == 0 {
            return 0.0;
        }

        // Trailing window: up to 168 hours (1 week) strictly in the past
        let window_start = current_idx.saturating_sub(168);
        let mut past_prices: Vec<f64> = dataset[window_start..current_idx]
            .iter()
            .map(|p| p.price_actual)
            .collect();

        if past_prices.len() < 24 {
            // Default heuristics if warm-up period
            let curr_p = dataset[current_idx].price_actual;
            if curr_p < 35.0 {
                return -max_power_mw; // Charge
            } else if curr_p > 85.0 {
                return max_power_mw; // Discharge
            } else {
                return 0.0;
            }
        }

        past_prices.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));
        let n = past_prices.len();
        let buy_idx = ((self.buy_pct / 100.0) * (n - 1) as f64).round() as usize;
        let sell_idx = ((self.sell_pct / 100.0) * (n - 1) as f64).round() as usize;

        let buy_threshold = past_prices[buy_idx];
        let sell_threshold = past_prices[sell_idx];
        let current_price = dataset[current_idx].price_actual;

        if current_price <= buy_threshold {
            -max_power_mw // Charge
        } else if current_price >= sell_threshold {
            max_power_mw // Discharge
        } else {
            0.0 // Idle
        }
    }
}
