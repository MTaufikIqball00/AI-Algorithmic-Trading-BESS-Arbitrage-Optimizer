use crate::state::AppState;
use axum::{extract::State, response::IntoResponse, Json};
use chrono::Utc;
use serde_json::json;

pub async fn health_handler(State(state): State<AppState>) -> impl IntoResponse {
    // Probe ML service connectivity
    let ml_health_url = format!("{}/health", state.ml_service_url);
    let ml_status = match state.http_client.get(&ml_health_url).send().await {
        Ok(resp) => {
            if resp.status().is_success() {
                "CONNECTED"
            } else {
                "DEGRADED"
            }
        }
        Err(_) => "DISCONNECTED",
    };

    let dataset_len = state.dataset.read().await.len();
    let kill_switch = state.risk_manager.is_kill_switch_active();

    Json(json!({
        "status": "healthy",
        "service": "bess-rust-control-plane",
        "version": env!("CARGO_PKG_VERSION"),
        "timestamp": Utc::now().to_rfc3339(),
        "database": "SQLITE_CONNECTED",
        "ml_service": {
            "status": ml_status,
            "url": state.ml_service_url
        },
        "market_dataset": {
            "loaded_records": dataset_len,
            "status": if dataset_len > 0 { "VALID" } else { "EMPTY" }
        },
        "risk_controls": {
            "emergency_kill_switch": kill_switch,
            "live_execution_locked": true
        }
    }))
}
