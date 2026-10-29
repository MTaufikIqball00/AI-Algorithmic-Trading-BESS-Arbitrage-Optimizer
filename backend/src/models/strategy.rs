use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum StrategyType {
    Idle,
    ThresholdHeuristic,
    ForecastHeuristic,
    PpoRl,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BacktestRequest {
    pub strategy: StrategyType,
    pub start_index: usize,
    pub end_index: Option<usize>,
    pub initial_soc: f64,
    pub battery_config: Option<crate::models::battery::BatteryConfig>,
    pub buy_threshold_pct: Option<f64>,  // e.g. 25.0
    pub sell_threshold_pct: Option<f64>, // e.g. 75.0
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EquityPoint {
    pub timestamp: String,
    pub price: f64,
    pub power_mw: f64,
    pub soc: f64,
    pub step_profit: f64,
    pub cumulative_pnl: f64,
    pub drawdown: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BacktestMetrics {
    pub strategy_name: String,
    pub total_steps: usize,
    pub gross_revenue: f64,
    pub charging_cost: f64,
    pub degradation_cost: f64,
    pub transaction_fees: f64,
    pub net_profit: f64,
    pub total_discharged_mwh: f64,
    pub total_charged_mwh: f64,
    pub total_throughput_mwh: f64,
    pub equivalent_full_cycles: f64,
    pub sharpe_ratio: f64,
    pub max_drawdown: f64,
    pub max_drawdown_pct: f64,
    pub win_rate_pct: f64,
    pub constraint_violations: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BacktestResponse {
    pub run_id: String,
    pub metrics: BacktestMetrics,
    pub equity_curve: Vec<EquityPoint>,
    pub baseline_comparisons: Vec<BacktestMetrics>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SensitivityParameterResult {
    pub parameter_value: f64,
    pub net_profit: f64,
    pub equivalent_full_cycles: f64,
    pub degradation_cost: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SensitivityAnalysisResponse {
    pub parameter_name: String,
    pub base_value: f64,
    pub curve: Vec<SensitivityParameterResult>,
}
