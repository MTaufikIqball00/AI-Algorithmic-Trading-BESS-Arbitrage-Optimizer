use crate::core::baselines::ThresholdHeuristic;
use crate::core::battery_twin::BatteryDigitalTwin;
use crate::state::AppState;
use axum::{extract::State, response::IntoResponse, Json};
use serde::Serialize;
use serde_json::json;

#[derive(Serialize)]
pub struct DispatchScheduleItem {
    pub hour_index: usize,
    pub timestamp: String,
    pub market_price: f64,
    pub day_ahead_price: f64,
    pub action_type: String, // "CHARGE", "DISCHARGE", "IDLE"
    pub recommended_power_mw: f64,
    pub projected_soc_pct: f64,
    pub predicted_revenue: f64,
    pub predicted_cost: f64,
    pub predicted_degradation_cost: f64,
    pub net_margin: f64,
    pub rationale: String,
}

#[derive(Serialize)]
pub struct DispatchPlanResponse {
    pub asset_id: String,
    pub plan_generated_at: String,
    pub initial_soc_pct: f64,
    pub final_projected_soc_pct: f64,
    pub total_predicted_net_pnl: f64,
    pub total_charge_mwh: f64,
    pub total_discharge_mwh: f64,
    pub schedule: Vec<DispatchScheduleItem>,
}

pub async fn get_dispatch_plan(State(state): State<AppState>) -> impl IntoResponse {
    let dataset = state.dataset.read().await;
    let config = state.battery_config.read().await.clone();
    let current_twin_soc = {
        let twin = state.twin.lock().await;
        twin.soc
    };

    if dataset.is_empty() {
        return Json(json!({
            "status": "empty",
            "message": "Dataset empty"
        }))
        .into_response();
    }

    // Lookahead 24 intervals (take the latest 24 rows as simulation target)
    let horizon = 24.min(dataset.len());
    let start_idx = dataset.len().saturating_sub(horizon);
    let slice = &dataset[start_idx..];

    let mut sim_twin = BatteryDigitalTwin::new(config.clone(), current_twin_soc);
    let heuristic = ThresholdHeuristic::new(25.0, 75.0);

    let mut schedule = Vec::new();
    let mut total_pnl = 0.0;
    let mut total_charge = 0.0;
    let mut total_discharge = 0.0;

    for (i, pt) in slice.iter().enumerate() {
        let req_power = heuristic.decide(start_idx + i, &dataset, config.power_mw);
        let step_res = sim_twin.step(req_power, 1.0, pt.price_actual);

        let action_type = if step_res.actual_power_mw > 0.1 {
            "DISCHARGE"
        } else if step_res.actual_power_mw < -0.1 {
            "CHARGE"
        } else {
            "IDLE"
        };

        if action_type == "CHARGE" {
            total_charge += step_res.actual_power_mw.abs();
        } else if action_type == "DISCHARGE" {
            total_discharge += step_res.actual_power_mw;
        }

        total_pnl += step_res.net_profit;

        let rationale = match action_type {
            "CHARGE" => format!(
                "Electricity price (${:.2}/MWh) is in lower 25th percentile. Rapid charge to capture low-cost energy.",
                pt.price_actual
            ),
            "DISCHARGE" => format!(
                "Evening peak pricing (${:.2}/MWh) detected. Discharging to maximize arbitrage spread over round-trip loss.",
                pt.price_actual
            ),
            _ => format!(
                "Price (${:.2}/MWh) within neutral band. Inverter idle to conserve cycle life and avoid degradation fees.",
                pt.price_actual
            ),
        };

        schedule.push(DispatchScheduleItem {
            hour_index: i + 1,
            timestamp: pt.timestamp.clone(),
            market_price: pt.price_actual,
            day_ahead_price: pt.price_day_ahead,
            action_type: action_type.to_string(),
            recommended_power_mw: (step_res.actual_power_mw * 100.0).round() / 100.0,
            projected_soc_pct: (step_res.new_soc * 100.0 * 10.0).round() / 10.0,
            predicted_revenue: (step_res.gross_revenue * 100.0).round() / 100.0,
            predicted_cost: (step_res.charging_cost * 100.0).round() / 100.0,
            predicted_degradation_cost: (step_res.degradation_cost * 100.0).round() / 100.0,
            net_margin: (step_res.net_profit * 100.0).round() / 100.0,
            rationale,
        });
    }

    let plan = DispatchPlanResponse {
        asset_id: config.asset_id.clone(),
        plan_generated_at: chrono::Utc::now().to_rfc3339(),
        initial_soc_pct: (current_twin_soc * 100.0 * 10.0).round() / 10.0,
        final_projected_soc_pct: (sim_twin.soc * 100.0 * 10.0).round() / 10.0,
        total_predicted_net_pnl: (total_pnl * 100.0).round() / 100.0,
        total_charge_mwh: (total_charge * 100.0).round() / 100.0,
        total_discharge_mwh: (total_discharge * 100.0).round() / 100.0,
        schedule,
    };

    Json(plan).into_response()
}
