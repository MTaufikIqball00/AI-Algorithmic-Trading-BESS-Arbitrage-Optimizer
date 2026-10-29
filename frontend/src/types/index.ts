export interface SystemHealth {
  status: string;
  service: string;
  version: string;
  timestamp: string;
  database: string;
  ml_service: {
    status: "CONNECTED" | "DEGRADED" | "DISCONNECTED";
    url: string;
  };
  market_dataset: {
    loaded_records: number;
    status: string;
  };
  risk_controls: {
    emergency_kill_switch: boolean;
    live_execution_locked: boolean;
  };
}

export interface MarketSummary {
  total_records: number;
  start_timestamp: string;
  end_timestamp: string;
  avg_price: number;
  min_price: number;
  max_price: number;
  std_price: number;
  negative_price_hours: number;
  market_id: string;
  data_status: string;
}

export interface MarketPoint {
  timestamp: string;
  market_id: string;
  price_actual: number;
  price_day_ahead: number;
  system_load_mw: number;
  solar_gen_mw: number;
  wind_gen_mw: number;
  temperature_c: number;
  data_quality: string;
}

export interface BatteryConfig {
  asset_id: string;
  name: string;
  capacity_mwh: number;
  power_mw: number;
  soc_min: number;
  soc_max: number;
  eta_charge: number;
  eta_discharge: number;
  cell_replacement_cost_per_mwh: number;
  cycle_life_nominal: number;
  transaction_fee_per_mwh: number;
  ramp_rate_mw_per_min: number;
}

export interface BatteryState {
  soc: number;
  active_power_mw: number;
  temperature_c: number;
  state_of_health_pct: number;
  total_throughput_mwh: number;
  equivalent_full_cycles: number;
  cumulative_degradation_cost: number;
}

export interface ForecastItem {
  timestamp: string;
  predicted_price: number;
  lower_bound_80: number;
  upper_bound_80: number;
  lower_bound_95: number;
  upper_bound_95: number;
  day_ahead_price: number;
}

export interface ForecastResponse {
  status: string;
  horizon_hours: number;
  predictions: ForecastItem[];
}

export interface ForecastMetrics {
  model_type: string;
  version: string;
  trained_at: string;
  samples_train: number;
  samples_val: number;
  samples_test: number;
  test_metrics: {
    mae: number;
    rmse: number;
    mape_percent: number;
    residual_std: number;
  };
  baseline_comparisons: {
    persistence_lag1: { mae: number; rmse: number };
    seasonal_naive_lag24: { mae: number; rmse: number };
    improvement_vs_naive_percent: number;
  };
  feature_importance: Record<string, number>;
  prediction_interval_std: number;
}

export interface EquityPoint {
  timestamp: string;
  price: number;
  power_mw: number;
  soc: number;
  step_profit: number;
  cumulative_pnl: number;
  drawdown: number;
}

export interface BacktestMetrics {
  strategy_name: string;
  total_steps: number;
  gross_revenue: number;
  charging_cost: number;
  degradation_cost: number;
  transaction_fees: number;
  net_profit: number;
  total_discharged_mwh: number;
  total_charged_mwh: number;
  total_throughput_mwh: number;
  equivalent_full_cycles: number;
  sharpe_ratio: number;
  max_drawdown: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  constraint_violations: number;
}

export interface BacktestResponse {
  run_id: string;
  metrics: BacktestMetrics;
  equity_curve: EquityPoint[];
  baseline_comparisons: BacktestMetrics[];
}

export interface SensitivityCurveItem {
  parameter_value: number;
  net_profit: number;
  equivalent_full_cycles: number;
  degradation_cost: number;
}

export interface SensitivityResponse {
  parameter_name: string;
  base_value: number;
  curve: SensitivityCurveItem[];
}

export interface DispatchScheduleItem {
  hour_index: number;
  timestamp: string;
  market_price: number;
  day_ahead_price: number;
  action_type: "CHARGE" | "DISCHARGE" | "IDLE";
  recommended_power_mw: number;
  projected_soc_pct: number;
  predicted_revenue: number;
  predicted_cost: number;
  predicted_degradation_cost: number;
  net_margin: number;
  rationale: string;
}

export interface DispatchPlanResponse {
  asset_id: string;
  plan_generated_at: string;
  initial_soc_pct: number;
  final_projected_soc_pct: number;
  total_predicted_net_pnl: number;
  total_charge_mwh: number;
  total_discharge_mwh: number;
  schedule: DispatchScheduleItem[];
}

export interface PaperOrder {
  order_id: string;
  timestamp: string;
  asset_id: string;
  side: "Charge" | "Discharge" | "Idle";
  requested_power_mw: number;
  filled_power_mw: number;
  limit_price: number | null;
  execution_price: number;
  status: "Pending" | "Filled" | "Rejected" | "Canceled";
  latency_ms: number;
  notes: string;
}

export interface AuditEvent {
  id: string;
  timestamp: string;
  event_type: string;
  severity: "INFO" | "WARN" | "CRITICAL";
  details: string;
}
