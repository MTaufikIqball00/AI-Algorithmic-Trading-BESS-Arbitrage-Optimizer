use backend::core::battery_twin::BatteryDigitalTwin;
use backend::models::battery::BatteryConfig;

#[test]
fn test_round_trip_efficiency_and_losses() {
    let config = BatteryConfig {
        capacity_mwh: 100.0,
        power_mw: 50.0,
        soc_min: 0.0,
        soc_max: 1.0,
        eta_charge: 0.90,
        eta_discharge: 0.90, // RT efficiency = 0.81 (81%)
        ..Default::default()
    };

    let mut twin = BatteryDigitalTwin::new(config, 0.0);

    // Charge 50 MW for 1 hour at price $20/MWh
    // Grid energy absorbed: 50 MWh
    // Internal energy stored: 50 * 0.90 = 45 MWh -> SoC becomes 0.45
    let ch_res = twin.step(-50.0, 1.0, 20.0);
    assert!(
        (twin.soc - 0.45).abs() < 1e-4,
        "Expected SoC 0.45, got {}",
        twin.soc
    );
    assert_eq!(ch_res.charging_cost, 1000.0); // 50 MWh * $20

    // Now discharge all 45 MWh internal energy at price $100/MWh
    // Energy delivered to grid: 45 * 0.90 = 40.5 MWh
    let dis_res = twin.step(50.0, 1.0, 100.0);
    assert!(
        (twin.soc - 0.0).abs() < 1e-4,
        "Expected SoC 0.0, got {}",
        twin.soc
    );
    assert!((dis_res.energy_delivered_mwh - 40.5).abs() < 1e-4);
    assert_eq!(dis_res.gross_revenue, 4050.0); // 40.5 MWh * $100

    // Total grid energy in: 50 MWh, Total grid energy out: 40.5 MWh
    // Net energy lost to heat: 9.5 MWh (exactly 19% loss, corresponding to 81% round-trip efficiency)
    assert!(dis_res.energy_delivered_mwh < ch_res.energy_delivered_mwh.abs());
}

#[test]
fn test_hard_soc_bounds_enforcement() {
    let config = BatteryConfig {
        soc_min: 0.10,
        soc_max: 0.90,
        capacity_mwh: 100.0,
        power_mw: 50.0,
        ..Default::default()
    };

    let mut twin = BatteryDigitalTwin::new(config, 0.50);

    // Try to charge excessively (10 hours of 50MW)
    for _ in 0..10 {
        twin.step(-50.0, 1.0, 10.0);
    }
    assert!(
        twin.soc <= 0.90 + 1e-6,
        "SoC breached upper bound: {}",
        twin.soc
    );

    // Try to discharge excessively (10 hours of 50MW)
    for _ in 0..10 {
        twin.step(50.0, 1.0, 100.0);
    }
    assert!(
        twin.soc >= 0.10 - 1e-6,
        "SoC breached lower bound: {}",
        twin.soc
    );
}
