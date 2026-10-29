use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MarketPoint {
    pub timestamp: String,
    pub market_id: String,
    pub price_actual: f64,
    pub price_day_ahead: f64,
    pub system_load_mw: f64,
    pub solar_gen_mw: f64,
    pub wind_gen_mw: f64,
    pub temperature_c: f64,
    pub data_quality: String, // "VALID", "STALE", "MISSING", "SYNTHETIC"
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MarketDataSummary {
    pub total_records: usize,
    pub start_timestamp: String,
    pub end_timestamp: String,
    pub avg_price: f64,
    pub min_price: f64,
    pub max_price: f64,
    pub std_price: f64,
    pub negative_price_hours: usize,
    pub market_id: String,
    pub data_status: String,
}
