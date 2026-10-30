use serde::{Deserialize, Serialize};

fn default_market_id() -> String {
    "CUSTOM_IMPORT".to_string()
}

fn default_quality() -> String {
    "VALID".to_string()
}

fn default_temp() -> f64 {
    20.0
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MarketPoint {
    pub timestamp: String,
    #[serde(default = "default_market_id")]
    pub market_id: String,
    pub price_actual: f64,
    #[serde(default)]
    pub price_day_ahead: f64,
    #[serde(default)]
    pub system_load_mw: f64,
    #[serde(default)]
    pub solar_gen_mw: f64,
    #[serde(default)]
    pub wind_gen_mw: f64,
    #[serde(default = "default_temp")]
    pub temperature_c: f64,
    #[serde(default = "default_quality")]
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
