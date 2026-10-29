use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderSide {
    Charge,
    Discharge,
    Idle,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum OrderStatus {
    Pending,
    Filled,
    Rejected,
    Canceled,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PaperOrder {
    pub order_id: String,
    pub timestamp: String,
    pub asset_id: String,
    pub side: OrderSide,
    pub requested_power_mw: f64,
    pub filled_power_mw: f64,
    pub limit_price: Option<f64>,
    pub execution_price: f64,
    pub status: OrderStatus,
    pub latency_ms: u64,
    pub notes: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct OrderSubmitRequest {
    pub asset_id: String,
    pub side: OrderSide,
    pub power_mw: f64,
    pub limit_price: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RiskCheckResult {
    pub passed: bool,
    pub reasons: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEvent {
    pub id: String,
    pub timestamp: String,
    pub event_type: String, // "ORDER_PLACED", "RISK_REJECTED", "KILL_SWITCH", "SYSTEM_START"
    pub severity: String,   // "INFO", "WARN", "CRITICAL"
    pub details: String,
}
