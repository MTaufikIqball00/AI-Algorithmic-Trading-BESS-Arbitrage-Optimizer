use crate::core::backtester::BacktestEngine;
use crate::models::strategy::BacktestRequest;
use crate::state::AppState;
use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde::Deserialize;
use serde_json::json;

pub async fn run_backtest(
    State(state): State<AppState>,
    Json(request): Json<BacktestRequest>,
) -> impl IntoResponse {
    let dataset = state.dataset.read().await;
    match BacktestEngine::run(&request, &dataset) {
        Ok(response) => {
            // Save run record to SQLite store
            let _ = state.store.save_backtest(&response).await;
            Json(response).into_response()
        }
        Err(err) => (StatusCode::BAD_REQUEST, Json(json!({ "error": err }))).into_response(),
    }
}

#[derive(Deserialize)]
pub struct SensitivityQuery {
    pub param: Option<String>,
}

pub async fn get_sensitivity_analysis(
    State(state): State<AppState>,
    Query(params): Query<SensitivityQuery>,
) -> impl IntoResponse {
    let dataset = state.dataset.read().await;
    let param_name = params
        .param
        .unwrap_or_else(|| "round_trip_efficiency".to_string());
    let response = BacktestEngine::sensitivity_analysis(&dataset, &param_name);
    Json(response).into_response()
}
