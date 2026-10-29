use backend::core::backtester::BacktestEngine;
use backend::models::market::MarketPoint;
use backend::models::strategy::{BacktestRequest, StrategyType};

fn sample_data() -> Vec<MarketPoint> {
    (0..100)
        .map(|i| {
            let p = 40.0 + 30.0 * (i as f64 * 0.2).sin();
            MarketPoint {
                timestamp: format!("2024-01-01T{:02}:00:00Z", i % 24),
                market_id: "CAISO_SP15".to_string(),
                price_actual: p,
                price_day_ahead: p * 0.98,
                system_load_mw: 22000.0,
                solar_gen_mw: 5000.0,
                wind_gen_mw: 2000.0,
                temperature_c: 20.0,
                data_quality: "VALID".to_string(),
            }
        })
        .collect()
}

#[test]
fn test_backtest_determinism_and_baselines() {
    let data = sample_data();
    let req = BacktestRequest {
        strategy: StrategyType::ThresholdHeuristic,
        start_index: 0,
        end_index: Some(100),
        initial_soc: 0.50,
        battery_config: None,
        buy_threshold_pct: Some(25.0),
        sell_threshold_pct: Some(75.0),
    };

    let res1 = BacktestEngine::run(&req, &data).expect("Backtest 1 failed");
    let res2 = BacktestEngine::run(&req, &data).expect("Backtest 2 failed");

    // Deterministic check: exact identical PnL and throughput
    assert_eq!(res1.metrics.net_profit, res2.metrics.net_profit);
    assert_eq!(
        res1.metrics.total_throughput_mwh,
        res2.metrics.total_throughput_mwh
    );
    assert_eq!(
        res1.metrics.equivalent_full_cycles,
        res2.metrics.equivalent_full_cycles
    );

    // Baseline comparisons must be present
    assert_eq!(res1.baseline_comparisons.len(), 3);
    assert_eq!(
        res1.baseline_comparisons[0].strategy_name,
        "Baseline: Idle (No Trade)"
    );
    assert_eq!(res1.baseline_comparisons[0].net_profit, 0.0);
    assert_eq!(res1.baseline_comparisons[0].total_throughput_mwh, 0.0);
}
