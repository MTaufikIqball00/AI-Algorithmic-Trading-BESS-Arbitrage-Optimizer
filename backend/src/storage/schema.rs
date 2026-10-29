pub const INIT_SCHEMA: &str = r#"
CREATE TABLE IF NOT EXISTS market_data (
    timestamp TEXT PRIMARY KEY,
    market_id TEXT NOT NULL,
    price_actual REAL NOT NULL,
    price_day_ahead REAL NOT NULL,
    system_load_mw REAL NOT NULL,
    solar_gen_mw REAL NOT NULL,
    wind_gen_mw REAL NOT NULL,
    temperature_c REAL NOT NULL,
    data_quality TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS paper_orders (
    order_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    side TEXT NOT NULL,
    requested_power_mw REAL NOT NULL,
    filled_power_mw REAL NOT NULL,
    limit_price REAL,
    execution_price REAL NOT NULL,
    status TEXT NOT NULL,
    latency_ms INTEGER NOT NULL,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS audit_trail (
    id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    details TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS backtest_runs (
    run_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    strategy_name TEXT NOT NULL,
    net_profit REAL NOT NULL,
    sharpe_ratio REAL NOT NULL,
    equivalent_full_cycles REAL NOT NULL,
    result_json TEXT NOT NULL
);
"#;
