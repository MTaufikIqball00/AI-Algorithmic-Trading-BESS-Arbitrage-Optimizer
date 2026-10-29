pub mod audit;
pub mod bess;
pub mod dispatch;
pub mod forecast;
pub mod health;
pub mod market;
pub mod orders;
pub mod strategy;

use crate::state::AppState;
use axum::{
    routing::{get, post},
    Router,
};

pub fn app_router(state: AppState) -> Router {
    Router::new()
        // Health & System
        .route("/api/health", get(health::health_handler))
        // Market Data
        .route("/api/market/summary", get(market::get_market_summary))
        .route("/api/market/points", get(market::get_market_points))
        .route("/api/market/import", post(market::import_market_csv))
        // Battery Digital Twin
        .route(
            "/api/bess/config",
            get(bess::get_bess_config).post(bess::update_bess_config),
        )
        .route("/api/bess/telemetry", get(bess::get_bess_telemetry))
        .route("/api/bess/reset", post(bess::reset_bess_twin))
        // Forecast
        .route("/api/forecast/predict", get(forecast::predict_forecast))
        .route("/api/forecast/train", post(forecast::train_forecast))
        .route("/api/forecast/metrics", get(forecast::get_forecast_metrics))
        // Strategy & Backtesting
        .route("/api/strategy/backtest", post(strategy::run_backtest))
        .route(
            "/api/strategy/sensitivity",
            get(strategy::get_sensitivity_analysis),
        )
        // Dispatch Planner
        .route("/api/dispatch/plan", get(dispatch::get_dispatch_plan))
        // Paper Bidding & Orders
        .route("/api/orders", get(orders::get_orders))
        .route("/api/orders/submit", post(orders::submit_order))
        .route("/api/orders/killswitch", post(orders::toggle_kill_switch))
        // Audit Trail
        .route("/api/audit/logs", get(audit::get_audit_logs))
        .with_state(state)
}
