use crate::models::battery::BatteryConfig;
use crate::models::order::{OrderSide, OrderStatus, OrderSubmitRequest, PaperOrder};
use chrono::Utc;
use uuid::Uuid;

pub trait MarketAdapter: Send + Sync {
    fn execute_order(
        &self,
        request: &OrderSubmitRequest,
        current_market_price: f64,
        config: &BatteryConfig,
    ) -> Result<PaperOrder, String>;

    fn is_live_trading_enabled(&self) -> bool;
    fn market_name(&self) -> &str;
}

pub struct PaperTradingAdapter {
    pub name: String,
}

impl Default for PaperTradingAdapter {
    fn default() -> Self {
        Self {
            name: "PAPER_EXCHANGE_SIMULATOR".to_string(),
        }
    }
}

impl MarketAdapter for PaperTradingAdapter {
    fn is_live_trading_enabled(&self) -> bool {
        false // strictly simulation
    }

    fn market_name(&self) -> &str {
        &self.name
    }

    fn execute_order(
        &self,
        request: &OrderSubmitRequest,
        current_market_price: f64,
        config: &BatteryConfig,
    ) -> Result<PaperOrder, String> {
        let order_id = format!("ORD-{}", Uuid::new_v4().to_string()[..8].to_uppercase());
        let filled_power = request.power_mw.min(config.power_mw);

        // Simulated slippage: ~0.15 $/MWh
        let slippage = match request.side {
            OrderSide::Charge => 0.15,
            OrderSide::Discharge => -0.15,
            OrderSide::Idle => 0.0,
        };
        let exec_price = (current_market_price + slippage * 0.1).round() * 100.0 / 100.0;

        Ok(PaperOrder {
            order_id,
            timestamp: Utc::now().to_rfc3339(),
            asset_id: request.asset_id.clone(),
            side: request.side.clone(),
            requested_power_mw: request.power_mw,
            filled_power_mw: filled_power,
            limit_price: request.limit_price,
            execution_price: exec_price,
            status: OrderStatus::Filled,
            latency_ms: 68,
            notes: "Paper execution filled by local simulator with realistic slippage".to_string(),
        })
    }
}

pub struct LiveMarketAdapter;

impl MarketAdapter for LiveMarketAdapter {
    fn is_live_trading_enabled(&self) -> bool {
        false // Hard-locked safety guard
    }

    fn market_name(&self) -> &str {
        "LIVE_MARKET_GATEWAY (LOCKED)"
    }

    fn execute_order(
        &self,
        _request: &OrderSubmitRequest,
        _price: f64,
        _config: &BatteryConfig,
    ) -> Result<PaperOrder, String> {
        Err("SECURITY REJECTION: Live ISO trading interface is NOT CONFIGURED. Live gateway requires verified credentials, scheduling coordinator authorization, and dual-party cryptographic sign-off.".to_string())
    }
}
