use crate::models::battery::BatteryConfig;
use crate::state::AppState;
use axum::{extract::State, response::IntoResponse, Json};
use serde_json::json;

pub async fn get_bess_config(State(state): State<AppState>) -> impl IntoResponse {
    let cfg = state.battery_config.read().await;
    Json(cfg.clone()).into_response()
}

pub async fn update_bess_config(
    State(state): State<AppState>,
    Json(new_config): Json<BatteryConfig>,
) -> impl IntoResponse {
    {
        let mut cfg = state.battery_config.write().await;
        *cfg = new_config.clone();
    }
    {
        let mut twin = state.twin.lock().await;
        twin.config = new_config;
    }
    Json(json!({
        "status": "success",
        "message": "Battery asset configuration updated successfully"
    }))
    .into_response()
}

pub async fn get_bess_telemetry(State(state): State<AppState>) -> impl IntoResponse {
    let twin = state.twin.lock().await;
    let telemetry = twin.get_state();
    Json(telemetry).into_response()
}

pub async fn reset_bess_twin(State(state): State<AppState>) -> impl IntoResponse {
    let cfg = state.battery_config.read().await.clone();
    let mut twin = state.twin.lock().await;
    *twin = crate::core::battery_twin::BatteryDigitalTwin::new(cfg, 0.50);
    Json(json!({
        "status": "success",
        "message": "Battery digital twin state reset to 50% SoC"
    }))
    .into_response()
}
