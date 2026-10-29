use std::env;

#[derive(Clone, Debug)]
pub struct AppConfig {
    pub host: String,
    pub port: u16,
    pub database_url: String,
    pub ml_service_url: String,
    pub dataset_path: String,
}

impl AppConfig {
    pub fn from_env() -> Self {
        dotenvy::dotenv().ok();

        let host = env::var("RUST_HOST").unwrap_or_else(|_| "127.0.0.1".to_string());
        let port = env::var("RUST_PORT")
            .ok()
            .and_then(|p| p.parse().ok())
            .unwrap_or(8230);
        let database_url = env::var("DATABASE_URL")
            .unwrap_or_else(|_| "sqlite://bess_optimizer.db?mode=rwc".to_string());
        let ml_service_url =
            env::var("ML_SERVICE_URL").unwrap_or_else(|_| "http://127.0.0.1:8231".to_string());
        let dataset_path = env::var("DATASET_PATH")
            .unwrap_or_else(|_| "data/datasets/caiso_hourly_benchmark_2024.csv".to_string());

        Self {
            host,
            port,
            database_url,
            ml_service_url,
            dataset_path,
        }
    }
}
