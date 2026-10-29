use crate::state::AppState;
use axum::{extract::State, http::StatusCode, response::IntoResponse, Json};
use serde_json::json;

pub async fn get_audit_logs(State(state): State<AppState>) -> impl IntoResponse {
    match state.store.get_audit_logs(100).await {
        Ok(logs) => Json(json!({
            "status": "success",
            "count": logs.len(),
            "logs": logs
        }))
        .into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("Failed to retrieve audit trail: {}", e) })),
        )
            .into_response(),
    }
}
