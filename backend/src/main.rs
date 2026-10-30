pub mod api;
pub mod config;
pub mod core;
pub mod models;
pub mod state;
pub mod storage;

use api::app_router;
use config::AppConfig;
use models::battery::BatteryConfig;
use models::market::MarketPoint;
use state::AppState;
use std::net::SocketAddr;
use std::path::Path;
use storage::sqlite_store::SqliteStore;
use tower_http::cors::{Any, CorsLayer};
use tracing::{info, warn};

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // 1. Initialize tracing
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "backend=info,tower_http=info".into()),
        )
        .init();

    info!("Starting AI Algorithmic Trading & BESS Arbitrage Optimizer Control Plane...");

    // 2. Load Configuration
    let config = AppConfig::from_env();
    info!("Target bind: {}:{}", config.host, config.port);
    info!("ML Service URL: {}", config.ml_service_url);

    // 3. Initialize SQLite Storage
    let store = SqliteStore::new(&config.database_url).await?;
    info!("SQLite database initialized at {}", config.database_url);

    // 4. Load Market Dataset
    let dataset = load_initial_dataset(&config.dataset_path);
    info!(
        "Loaded {} interval points from {}",
        dataset.len(),
        config.dataset_path
    );

    // 5. Initialize Application State
    let battery_config = BatteryConfig::default();
    let state = AppState::new(battery_config, dataset, store, config.ml_service_url);

    // 6. Setup CORS & Router
    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let app = app_router(state)
        .layer(cors)
        .layer(axum::extract::DefaultBodyLimit::max(100 * 1024 * 1024));

    // 7. Bind Server
    let addr: SocketAddr = format!("{}:{}", config.host, config.port).parse()?;
    info!("BESS Control Plane listening on http://{}", addr);

    let listener = tokio::net::TcpListener::bind(addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}

fn load_initial_dataset(path_str: &str) -> Vec<MarketPoint> {
    let mut candidate = Path::new(path_str).to_path_buf();
    if !candidate.exists() {
        let parent_candidate = Path::new("..").join(path_str);
        if parent_candidate.exists() {
            candidate = parent_candidate;
        } else {
            warn!(
                "Dataset file not found at {} or {}. Starting with empty dataset.",
                path_str,
                Path::new("..").join(path_str).display()
            );
            return Vec::new();
        }
    }

    let mut points = Vec::new();
    match csv::Reader::from_path(&candidate) {
        Ok(mut rdr) => {
            for record in rdr.deserialize().flatten() {
                points.push(record);
            }
        }
        Err(e) => {
            warn!("Failed to read CSV at {}: {}", candidate.display(), e);
        }
    }
    points
}
