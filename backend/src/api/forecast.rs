use crate::state::AppState;
use axum::{
    extract::{Query, State},
    response::IntoResponse,
    Json,
};
use serde::Deserialize;
use serde_json::json;

#[derive(Deserialize)]
pub struct ForecastPredictQuery {
    pub horizon: Option<usize>,
}

pub async fn predict_forecast(
    State(state): State<AppState>,
    Query(params): Query<ForecastPredictQuery>,
) -> impl IntoResponse {
    let horizon = params.horizon.unwrap_or(24).min(168);
    let ml_url = format!("{}/forecast/predict", state.ml_service_url);

    let dataset_path = crate::api::market::get_active_dataset_path();

    // Call ML service
    let res = state
        .http_client
        .post(&ml_url)
        .json(&json!({
            "horizon": horizon,
            "dataset_path": dataset_path
        }))
        .send()
        .await;

    match res {
        Ok(resp) if resp.status().is_success() => {
            let data: serde_json::Value = resp.json().await.unwrap_or_default();
            Json(data).into_response()
        }
        _ => {
            // Fallback using Day-Ahead market prices from dataset
            let ds = state.dataset.read().await;
            let recent_slice = ds.iter().rev().take(horizon).cloned().collect::<Vec<_>>();
            let mut predictions = Vec::new();

            for pt in recent_slice.into_iter().rev() {
                let p = pt.price_day_ahead;
                predictions.push(json!({
                    "timestamp": pt.timestamp,
                    "predicted_price": p,
                    "lower_bound_80": (p - 8.0).round() * 100.0 / 100.0,
                    "upper_bound_80": (p + 8.0).round() * 100.0 / 100.0,
                    "lower_bound_95": (p - 15.0).round() * 100.0 / 100.0,
                    "upper_bound_95": (p + 15.0).round() * 100.0 / 100.0,
                    "day_ahead_price": p
                }));
            }

            Json(json!({
                "status": "fallback",
                "message": "Serving ISO Day-Ahead forward prices (ML service offline)",
                "horizon_hours": horizon,
                "predictions": predictions
            }))
            .into_response()
        }
    }
}

pub async fn train_forecast(State(state): State<AppState>) -> impl IntoResponse {
    let ml_url = format!("{}/forecast/train", state.ml_service_url);
    let dataset_path = crate::api::market::get_active_dataset_path();
    let res = state
        .http_client
        .post(&ml_url)
        .json(&json!({
            "dataset_path": dataset_path
        }))
        .send()
        .await;

    match res {
        Ok(resp) if resp.status().is_success() => {
            let data: serde_json::Value = resp.json().await.unwrap_or_default();
            Json(data).into_response()
        }
        Ok(resp) => Json(json!({
            "status": "error",
            "message": format!("ML service returned status {}", resp.status())
        }))
        .into_response(),
        Err(e) => Json(json!({
            "status": "error",
            "message": format!("Failed to reach ML service: {}", e)
        }))
        .into_response(),
    }
}

pub async fn get_forecast_metrics(State(state): State<AppState>) -> impl IntoResponse {
    let ml_url = format!("{}/forecast/metrics", state.ml_service_url);
    let res = state.http_client.get(&ml_url).send().await;

    match res {
        Ok(resp) if resp.status().is_success() => {
            let data: serde_json::Value = resp.json().await.unwrap_or_default();
            Json(data).into_response()
        }
        _ => Json(json!({
            "status": "offline",
            "message": "ML service metrics currently unavailable"
        }))
        .into_response(),
    }
}
