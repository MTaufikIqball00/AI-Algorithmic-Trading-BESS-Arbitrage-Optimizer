use crate::core::battery_twin::BatteryDigitalTwin;
use crate::core::market_adapter::{LiveMarketAdapter, PaperTradingAdapter};
use crate::core::risk_manager::RiskManager;
use crate::models::battery::BatteryConfig;
use crate::models::market::MarketPoint;
use crate::storage::sqlite_store::SqliteStore;
use std::sync::Arc;
use tokio::sync::{Mutex, RwLock};

#[derive(Clone)]
pub struct AppState {
    pub battery_config: Arc<RwLock<BatteryConfig>>,
    pub twin: Arc<Mutex<BatteryDigitalTwin>>,
    pub dataset: Arc<RwLock<Vec<MarketPoint>>>,
    pub risk_manager: Arc<RiskManager>,
    pub paper_adapter: Arc<PaperTradingAdapter>,
    pub live_adapter: Arc<LiveMarketAdapter>,
    pub store: SqliteStore,
    pub ml_service_url: String,
    pub http_client: reqwest::Client,
}

impl AppState {
    pub fn new(
        config: BatteryConfig,
        dataset: Vec<MarketPoint>,
        store: SqliteStore,
        ml_service_url: String,
    ) -> Self {
        let twin = BatteryDigitalTwin::new(config.clone(), 0.50);
        Self {
            battery_config: Arc::new(RwLock::new(config)),
            twin: Arc::new(Mutex::new(twin)),
            dataset: Arc::new(RwLock::new(dataset)),
            risk_manager: Arc::new(RiskManager::new()),
            paper_adapter: Arc::new(PaperTradingAdapter::default()),
            live_adapter: Arc::new(LiveMarketAdapter),
            store,
            ml_service_url,
            http_client: reqwest::Client::builder()
                .timeout(std::time::Duration::from_secs(10))
                .build()
                .unwrap_or_default(),
        }
    }
}
