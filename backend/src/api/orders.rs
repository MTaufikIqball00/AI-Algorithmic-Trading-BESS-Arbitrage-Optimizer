use crate::core::market_adapter::MarketAdapter;
use crate::models::order::{AuditEvent, OrderSide, OrderSubmitRequest};
use crate::state::AppState;
use axum::{extract::State, http::StatusCode, response::IntoResponse, Json};
use chrono::Utc;
use serde::Deserialize;
use serde_json::json;
use uuid::Uuid;

pub async fn get_orders(State(state): State<AppState>) -> impl IntoResponse {
    match state.store.get_orders(50).await {
        Ok(orders) => Json(json!({
            "status": "success",
            "count": orders.len(),
            "orders": orders
        }))
        .into_response(),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(json!({ "error": format!("Failed to fetch orders: {}", e) })),
        )
            .into_response(),
    }
}

pub async fn submit_order(
    State(state): State<AppState>,
    Json(request): Json<OrderSubmitRequest>,
) -> impl IntoResponse {
    let config = state.battery_config.read().await.clone();
    let current_soc = {
        let twin = state.twin.lock().await;
        twin.soc
    };

    // 1. Run Pre-Trade Risk Manager Validation
    let risk_res = state
        .risk_manager
        .validate_order(&request, &config, current_soc);

    if !risk_res.passed {
        let audit = AuditEvent {
            id: Uuid::new_v4().to_string(),
            timestamp: Utc::now().to_rfc3339(),
            event_type: "ORDER_RISK_REJECTED".to_string(),
            severity: "WARN".to_string(),
            details: format!(
                "Order for {:.1} MW ({:?}) rejected by Risk Manager: {}",
                request.power_mw,
                request.side,
                risk_res.reasons.join("; ")
            ),
        };
        let _ = state.store.log_audit(&audit).await;

        return (
            StatusCode::UNPROCESSABLE_ENTITY,
            Json(json!({
                "status": "rejected",
                "risk_passed": false,
                "reasons": risk_res.reasons
            })),
        )
            .into_response();
    }

    // 2. Fetch latest market price
    let latest_price = {
        let ds = state.dataset.read().await;
        ds.last().map(|p| p.price_actual).unwrap_or(55.0)
    };

    // 3. Execute via PaperTradingAdapter
    let order_res = state
        .paper_adapter
        .execute_order(&request, latest_price, &config);

    match order_res {
        Ok(order) => {
            // Apply fill to Digital Twin state
            let req_power = match order.side {
                OrderSide::Charge => -order.filled_power_mw,
                OrderSide::Discharge => order.filled_power_mw,
                OrderSide::Idle => 0.0,
            };
            {
                let mut twin = state.twin.lock().await;
                twin.step(req_power, 1.0, order.execution_price);
            }

            // Save to DB and audit log
            let _ = state.store.save_order(&order).await;
            let audit = AuditEvent {
                id: Uuid::new_v4().to_string(),
                timestamp: Utc::now().to_rfc3339(),
                event_type: "ORDER_FILLED".to_string(),
                severity: "INFO".to_string(),
                details: format!(
                    "Paper order {} filled: {:.1} MW at ${:.2}/MWh",
                    order.order_id, order.filled_power_mw, order.execution_price
                ),
            };
            let _ = state.store.log_audit(&audit).await;

            Json(json!({
                "status": "success",
                "risk_passed": true,
                "order": order
            }))
            .into_response()
        }
        Err(e) => (StatusCode::BAD_REQUEST, Json(json!({ "error": e }))).into_response(),
    }
}

#[derive(Deserialize)]
pub struct KillSwitchRequest {
    pub active: bool,
}

pub async fn toggle_kill_switch(
    State(state): State<AppState>,
    Json(payload): Json<KillSwitchRequest>,
) -> impl IntoResponse {
    state.risk_manager.set_kill_switch(payload.active);

    let audit = AuditEvent {
        id: Uuid::new_v4().to_string(),
        timestamp: Utc::now().to_rfc3339(),
        event_type: "KILL_SWITCH_TOGGLE".to_string(),
        severity: if payload.active { "CRITICAL" } else { "INFO" }.to_string(),
        details: format!(
            "Emergency Kill-Switch state set to: {}",
            if payload.active { "ACTIVE" } else { "DISARMED" }
        ),
    };
    let _ = state.store.log_audit(&audit).await;

    Json(json!({
        "status": "success",
        "kill_switch_active": payload.active,
        "message": if payload.active {
            "Emergency Kill-Switch ACTIVATED. All trading orders halted."
        } else {
            "Emergency Kill-Switch DISARMED. Trading orders permitted."
        }
    }))
    .into_response()
}
