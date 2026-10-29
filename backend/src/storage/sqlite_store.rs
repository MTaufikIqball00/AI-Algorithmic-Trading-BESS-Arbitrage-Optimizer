use crate::models::order::{AuditEvent, PaperOrder};
use crate::models::strategy::BacktestResponse;
use crate::storage::schema::INIT_SCHEMA;
use chrono::Utc;
use sqlx::{sqlite::SqlitePoolOptions, Pool, Sqlite};
use uuid::Uuid;

#[derive(Clone)]
pub struct SqliteStore {
    pool: Pool<Sqlite>,
}

impl SqliteStore {
    pub async fn new(database_url: &str) -> Result<Self, sqlx::Error> {
        let pool = SqlitePoolOptions::new()
            .max_connections(5)
            .connect(database_url)
            .await?;

        sqlx::raw_sql(INIT_SCHEMA).execute(&pool).await?;

        // Seed initial audit log
        let init_event = AuditEvent {
            id: Uuid::new_v4().to_string(),
            timestamp: Utc::now().to_rfc3339(),
            event_type: "SYSTEM_INITIALIZE".to_string(),
            severity: "INFO".to_string(),
            details: "BESS Storage Engine and SQLite database initialized successfully".to_string(),
        };
        let store = Self { pool };
        let _ = store.log_audit(&init_event).await;

        Ok(store)
    }

    pub async fn log_audit(&self, event: &AuditEvent) -> Result<(), sqlx::Error> {
        sqlx::query(
            "INSERT INTO audit_trail (id, timestamp, event_type, severity, details) VALUES (?, ?, ?, ?, ?)"
        )
        .bind(&event.id)
        .bind(&event.timestamp)
        .bind(&event.event_type)
        .bind(&event.severity)
        .bind(&event.details)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    pub async fn get_audit_logs(&self, limit: i64) -> Result<Vec<AuditEvent>, sqlx::Error> {
        let rows = sqlx::query_as::<_, (String, String, String, String, String)>(
            "SELECT id, timestamp, event_type, severity, details FROM audit_trail ORDER BY timestamp DESC LIMIT ?"
        )
        .bind(limit)
        .fetch_all(&self.pool)
        .await?;

        let logs = rows
            .into_iter()
            .map(
                |(id, timestamp, event_type, severity, details)| AuditEvent {
                    id,
                    timestamp,
                    event_type,
                    severity,
                    details,
                },
            )
            .collect();
        Ok(logs)
    }

    pub async fn save_order(&self, order: &PaperOrder) -> Result<(), sqlx::Error> {
        let side_str = format!("{:?}", order.side);
        let status_str = format!("{:?}", order.status);

        sqlx::query(
            "INSERT INTO paper_orders (order_id, timestamp, asset_id, side, requested_power_mw, filled_power_mw, limit_price, execution_price, status, latency_ms, notes) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
        )
        .bind(&order.order_id)
        .bind(&order.timestamp)
        .bind(&order.asset_id)
        .bind(&side_str)
        .bind(order.requested_power_mw)
        .bind(order.filled_power_mw)
        .bind(order.limit_price)
        .bind(order.execution_price)
        .bind(&status_str)
        .bind(order.latency_ms as i64)
        .bind(&order.notes)
        .execute(&self.pool)
        .await?;
        Ok(())
    }

    pub async fn get_orders(&self, limit: i64) -> Result<Vec<PaperOrder>, sqlx::Error> {
        let rows = sqlx::query_as::<_, (String, String, String, String, f64, f64, Option<f64>, f64, String, i64, Option<String>)>(
            "SELECT order_id, timestamp, asset_id, side, requested_power_mw, filled_power_mw, limit_price, execution_price, status, latency_ms, notes FROM paper_orders ORDER BY timestamp DESC LIMIT ?"
        )
        .bind(limit)
        .fetch_all(&self.pool)
        .await?;

        let orders = rows
            .into_iter()
            .map(
                |(
                    order_id,
                    timestamp,
                    asset_id,
                    side_str,
                    req_p,
                    fill_p,
                    limit_p,
                    exec_p,
                    stat_str,
                    lat,
                    notes,
                )| {
                    let side = match side_str.as_str() {
                        "Charge" => crate::models::order::OrderSide::Charge,
                        "Discharge" => crate::models::order::OrderSide::Discharge,
                        _ => crate::models::order::OrderSide::Idle,
                    };
                    let status = match stat_str.as_str() {
                        "Filled" => crate::models::order::OrderStatus::Filled,
                        "Rejected" => crate::models::order::OrderStatus::Rejected,
                        "Canceled" => crate::models::order::OrderStatus::Canceled,
                        _ => crate::models::order::OrderStatus::Pending,
                    };
                    PaperOrder {
                        order_id,
                        timestamp,
                        asset_id,
                        side,
                        requested_power_mw: req_p,
                        filled_power_mw: fill_p,
                        limit_price: limit_p,
                        execution_price: exec_p,
                        status,
                        latency_ms: lat as u64,
                        notes: notes.unwrap_or_default(),
                    }
                },
            )
            .collect();
        Ok(orders)
    }

    pub async fn save_backtest(&self, res: &BacktestResponse) -> Result<(), sqlx::Error> {
        let json_str = serde_json::to_string(res).unwrap_or_default();
        sqlx::query(
            "INSERT INTO backtest_runs (run_id, timestamp, strategy_name, net_profit, sharpe_ratio, equivalent_full_cycles, result_json) VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        .bind(&res.run_id)
        .bind(Utc::now().to_rfc3339())
        .bind(&res.metrics.strategy_name)
        .bind(res.metrics.net_profit)
        .bind(res.metrics.sharpe_ratio)
        .bind(res.metrics.equivalent_full_cycles)
        .bind(json_str)
        .execute(&self.pool)
        .await?;
        Ok(())
    }
}
