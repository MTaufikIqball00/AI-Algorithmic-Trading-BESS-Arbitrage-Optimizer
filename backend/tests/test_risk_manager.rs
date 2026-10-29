use backend::core::risk_manager::RiskManager;
use backend::models::battery::BatteryConfig;
use backend::models::order::{OrderSide, OrderSubmitRequest};

#[test]
fn test_kill_switch_blocks_orders() {
    let risk_manager = RiskManager::new();
    let config = BatteryConfig::default();

    let order = OrderSubmitRequest {
        asset_id: "BESS_1".to_string(),
        side: OrderSide::Charge,
        power_mw: 20.0,
        limit_price: None,
    };

    // Initially active should pass
    let res = risk_manager.validate_order(&order, &config, 0.50);
    assert!(res.passed);

    // Activate Kill-Switch
    risk_manager.set_kill_switch(true);
    let blocked_res = risk_manager.validate_order(&order, &config, 0.50);
    assert!(!blocked_res.passed);
    assert!(blocked_res.reasons[0].contains("Kill-Switch"));
}

#[test]
fn test_inverter_power_rating_limit() {
    let risk_manager = RiskManager::new();
    let config = BatteryConfig {
        power_mw: 50.0,
        ..Default::default()
    };

    let excess_order = OrderSubmitRequest {
        asset_id: "BESS_1".to_string(),
        side: OrderSide::Discharge,
        power_mw: 75.0, // Exceeds 50 MW rating
        limit_price: None,
    };

    let res = risk_manager.validate_order(&excess_order, &config, 0.80);
    assert!(!res.passed);
    assert!(res.reasons[0].contains("exceeds inverter physical rating"));
}
