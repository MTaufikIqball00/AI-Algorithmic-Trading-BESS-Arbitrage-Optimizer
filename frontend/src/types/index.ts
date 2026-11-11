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

export interface SolarPvForecastPoint {
  asset_id: string;
  timestamp: string;
  forecast_horizon_minutes: number;
  predicted_power_kw: number;
  predicted_power_mw: number;
  predicted_energy_kwh: number;
  predicted_energy_mwh: number;
  prediction_interval: {
    lower_80: number;
    upper_80: number;
    lower_95: number;
    upper_95: number;
  };
  model_version: string;
  data_quality: string;
  source_type: string;
}

export interface SolarCoupledDispatchDecision {
  timestamp: string;
  solar_available_mw: number;
  solar_to_load_mw: number;
  solar_to_bess_charge_mw: number;
  solar_to_grid_export_mw: number;
  solar_curtailed_mw: number;
  bess_grid_charge_mw: number;
  bess_discharge_mw: number;
  net_grid_export_mw: number;
  resulting_soc: number;
  constraint_violated: boolean;
  notes: string;
}

export interface SolarPvSummaryResponse {
  status: string;
  asset_id: string;
  dataset_path: string;
  rated_dc_kw: number;
  rated_ac_kw: number;
  total_intervals: number;
  archive_summary: Record<string, any>;
  xgboost_metadata: Record<string, any>;
  lightgbm_metadata: Record<string, any>;
  forecast: {
    site_id: string;
    generated_at: string;
    horizon_hours: number;
    total_forecast_energy_mwh: number;
    peak_forecast_power_mw: number;
    points: SolarPvForecastPoint[];
  };
  soiling: {
    status: string;
    soiling_ratio_current: number | null;
    estimated_soiling_rate_pct_day: number | null;
    cleaning_events_detected: number;
    wash_recovery_pct: number | null;
    analyzed_days: number;
    evidence_notes: string[];
    missing_evidence: string[];
  };
  degradation: {
    status: string;
    annualized_degradation_pct_year: number | null;
    confidence_interval_95: [number, number] | null;
    data_duration_days: number;
    is_statistically_defensible: boolean;
    normalization_method: string;
    sample_points_analyzed: number;
    scientific_warning: string | null;
    evidence_notes: string[];
  };
  anomaly_summary: {
    total_detected: number;
    events: Array<{
      event_id: string;
      asset_id: string;
      start_timestamp: string;
      end_timestamp: string;
      classification: string;
      severity: string;
      confidence: number | null;
      evidence: {
        mean_irradiance_poa: number;
        mean_expected_power_kw: number;
        mean_actual_power_kw: number;
        power_deficit_pct: number;
        inverter_status_observed: string;
        evidence_notes: string[];
      };
    }>;
  };
  maintenance: {
    recommendation_count: number;
    recommendations: Array<{
      recommendation_id: string;
      asset_id: string;
      priority: string;
      analysis_period: string;
      reason: string;
      evidence: string[];
      recommended_inspection: string;
      uncertainty: string;
      data_limitations: string[];
    }>;
  };
  coupled_dispatch_example: SolarCoupledDispatchDecision;
}

