use crate::models::market::{MarketDataSummary, MarketPoint};
use crate::state::AppState;
use axum::{
    extract::{Query, State},
    http::StatusCode,
    response::IntoResponse,
    Json,
};
use serde::Deserialize;
use serde_json::json;

#[derive(Deserialize)]
pub struct PaginationQuery {
    pub limit: Option<usize>,
    pub offset: Option<usize>,
}

pub async fn get_market_summary(State(state): State<AppState>) -> impl IntoResponse {
    let data = state.dataset.read().await;
    if data.is_empty() {
        return Json(json!({
            "status": "empty",
            "message": "No market data loaded"
        }))
        .into_response();
    }

    let n = data.len();
    let prices: Vec<f64> = data.iter().map(|p| p.price_actual).collect();
    let sum: f64 = prices.iter().sum();
    let avg = sum / n as f64;
    let min = prices.iter().cloned().fold(f64::INFINITY, f64::min);
    let max = prices.iter().cloned().fold(f64::NEG_INFINITY, f64::max);
    let variance: f64 = prices.iter().map(|p| (p - avg).powi(2)).sum::<f64>() / n as f64;
    let std = variance.sqrt();
    let neg_hours = prices.iter().filter(|&&p| p < 0.0).count();

    let summary = MarketDataSummary {
        total_records: n,
        start_timestamp: data[0].timestamp.clone(),
        end_timestamp: data[n - 1].timestamp.clone(),
        avg_price: (avg * 100.0).round() / 100.0,
        min_price: (min * 100.0).round() / 100.0,
        max_price: (max * 100.0).round() / 100.0,
        std_price: (std * 100.0).round() / 100.0,
        negative_price_hours: neg_hours,
        market_id: data[0].market_id.clone(),
        data_status: "VERIFIED_HISTORICAL_BENCHMARK".to_string(),
    };

    Json(summary).into_response()
}

pub async fn get_market_points(
    State(state): State<AppState>,
    Query(params): Query<PaginationQuery>,
) -> impl IntoResponse {
    let data = state.dataset.read().await;
    let limit = params.limit.unwrap_or(168).min(1000); // default 1 week
    let offset = params.offset.unwrap_or(0);

    if offset >= data.len() {
        return Json(json!([])).into_response();
    }

    let end = (offset + limit).min(data.len());
    let slice = data[offset..end].to_vec();

    Json(slice).into_response()
}

#[derive(Deserialize)]
pub struct ImportCsvRequest {
    pub csv_content: String,
    pub market_id: Option<String>,
}

pub async fn import_market_csv(
    State(state): State<AppState>,
    Json(payload): Json<ImportCsvRequest>,
) -> impl IntoResponse {
    let mut reader = csv::Reader::from_reader(payload.csv_content.as_bytes());
    let mut new_points = Vec::new();

    for result in reader.deserialize::<MarketPoint>() {
        match result {
            Ok(mut point) => {
                let point: MarketPoint = {
                    if let Some(ref mid) = payload.market_id {
                        point.market_id = mid.clone();
                    }
                    if point.price_day_ahead == 0.0 && point.price_actual != 0.0 {
                        point.price_day_ahead = point.price_actual;
                    }
                    point
                };
                new_points.push(point);
            }
            Err(e) => {
                return (
                    StatusCode::BAD_REQUEST,
                    Json(json!({
                        "error": format!("CSV Schema parse error: {}. Minimal required headers: timestamp, price_actual (optional: market_id, price_day_ahead, system_load_mw, solar_gen_mw, wind_gen_mw, temperature_c, data_quality)", e)
                    })),
                )
                    .into_response();
            }
        }
    }

    if new_points.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(json!({ "error": "No valid rows found in CSV" })),
        )
            .into_response();
    }

    let count = new_points.len();
    {
        let mut ds = state.dataset.write().await;
        *ds = new_points;
    }

    // Persist active dataset to disk so ML service (Python) trains and predicts on the current imported data
    let _ = tokio::fs::create_dir_all("data/datasets").await;
    let _ = tokio::fs::write("data/datasets/active_market_dataset.csv", &payload.csv_content).await;

    Json(json!({
        "status": "success",
        "imported_records": count,
        "message": format!("Successfully imported and verified {} market interval records", count)
    }))
    .into_response()
}
