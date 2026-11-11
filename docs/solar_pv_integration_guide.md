# Solar PV Data Science & BESS Arbitrage Integration Guide

## 1. Overview & Architectural Principles

The **Solar PV Data Science Module** is an analytical and predictive extension designed specifically for the **AI Algorithmic Trading & BESS Arbitrage Optimizer** platform.

### Core Scientific Principles:
1. **Evidence-Based Causality**: A reduction in photovoltaic power does **NOT** automatically imply soiling, cell degradation, or hardware failure. Reductions are categorized using multi-criteria physical telemetry (irradiance, cloud cover, cell temperature, DC voltage, DC current, inverter status, sensor diagnostics). When evidence is insufficient or conflicting, the system outputs `UNKNOWN_NEEDS_INVESTIGATION` with an uncalibrated confidence (`None`).
2. **Zero Future Lookahead**: All feature transformations, rolling statistics, and lag operations strictly utilize past observations (`shift(1)` or greater), preventing data snooping and lookahead leakage in forecasting.
3. **Rigorous Physical Modeling**: Power calculations ($P = V \times I$), numerical energy integrations ($\int P dt$), temperature deratings ($1 + \gamma(T_{\text{cell}} - 25)$), and Performance Ratios ($PR = Y_f / Y_r$) adhere strictly to **IEC 61724** and Sandia/NREL solar standards.
4. **Conservation of Energy & Zero Double-Counting**: In hybrid solar-storage dispatch, every kilowatt of generated solar energy is accounted for across load supply, battery charging, grid export, or physical curtailment. Battery State of Charge (SoC), charge/discharge headroom, round-trip efficiency ($\eta_{\text{charge}}$), and Point of Interconnection (POI) limits are mathematically enforced.
5. **No Architectural Bloat**: The module runs within the existing **FastAPI ML Microservice (Port 8231)** without requiring new server ports, databases, or redundant daemons.

---

## 2. Directory Structure

```text
solar_pv/
├── __init__.py
├── config/
│   ├── __init__.py
│   └── defaults.py                  # Physical constants, STC values, PVSystemConfig
├── data/
│   ├── __init__.py
│   ├── dictionary.py                # Comprehensive PV Data Dictionary & Governance
│   ├── provenance.py                # SourceType, licensing & audit provenance
│   ├── validation/
│   │   ├── __init__.py
│   │   └── validator.py             # Timestamp ordering, duplicate checks, physical range bounding
│   ├── cleaning/
│   │   ├── __init__.py
│   │   └── cleaner.py               # Time-aware interpolation, sentinel cleanup, audit lineage
│   ├── weather/
│   │   ├── __init__.py
│   │   └── adapter.py               # Solar position (zenith, azimuth), clear-sky GHI, POA transposition
│   └── ingestion/
│       ├── __init__.py
│       ├── synthetic.py             # Deterministic physics-based synthetic generator (seed=42)
│       ├── nrel_pvdaq.py            # Official NREL PVDAQ / OEDI cloud ingestion adapter
│       └── csv_importer.py          # Generic SCADA/CSV importer with auto-header mapping
├── features/
│   ├── __init__.py
│   ├── solar_physics.py             # P=VI, trapezoidal energy integration, STC expected power, IEC 61724 PR
│   └── engineering.py               # Causal lag features, rolling statistics, astronomical features
├── forecasting/
│   ├── __init__.py
│   ├── baseline.py                  # Lag-1, Lag-24 seasonal naive, and night-zero persistence baselines
│   ├── time_series.py               # Chronological 70/15/15 splitter and walk-forward cross-validation
│   ├── evaluation.py                # MAE, RMSE, daylight-safe MAPE, sMAPE, R2, and PICP coverage
│   ├── xgboost_model.py             # XGBoost regressor with 80% & 95% uncertainty intervals
│   └── lightgbm_model.py            # LightGBM regressor with early stopping & baseline comparison
├── anomaly_detection/
│   ├── __init__.py
│   ├── evidence.py                  # Anomaly taxonomy, EvidenceBundle, and AnomalyEvent dataclass
│   ├── detection.py                 # Physical residual analysis, MAD robust Z-score, Isolation Forest
│   └── classification.py            # Multi-criteria evidence classifier (Weather vs Soiling vs Hardware vs Sensor vs Unknown)
├── soiling/
│   ├── __init__.py
│   └── analysis.py                  # Daily irradiance-weighted PR, wash recovery step, missing evidence reporting
├── degradation/
│   ├── __init__.py
│   ├── trend.py                     # Theil-Sen non-parametric estimator, OLS with HAC standard errors
│   └── analysis.py                  # Long-term degradation analyzer with strict 365-day sufficiency gate
├── maintenance/
│   ├── __init__.py
│   ├── risk_scoring.py              # Recurrence, severity, and persistent loss asset health index
│   └── recommendations.py           # Condition-based maintenance priorities (Critical, High, Medium, Low, Monitoring)
├── integration/
│   ├── __init__.py
│   ├── bess_contracts.py            # Typed Pydantic schemas (PVForecastPayload, CoupledDispatchConstraint)
│   ├── adapters.py                  # Energy-conserving solar-plus-storage dispatch adapter
│   └── router.py                    # FastAPI APIRouter mounted cleanly on ml_service (Port 8231)
└── tests/
    ├── __init__.py
    ├── test_validation.py           # Timestamp ordering, duplicate detection, range checks
    ├── test_cleaning.py             # Sentinel replacement, bounded interpolation, nighttime zero
    ├── test_physics.py              # P=VI, trapezoidal integration, STC expected power, PR
    ├── test_features_and_leakage.py # Shift(1) causal feature verification, solar geometry
    ├── test_forecasting.py          # Chronological splits, walk-forward CV, baseline comparisons, XGB/LGB training
    ├── test_anomaly_and_unknown.py  # Evidence-based classification, night-zero exclusion, unknown fallback
    ├── test_soiling_and_degradation.py # Cleaning wash recovery, 365-day sufficiency gate
    └── test_maintenance_and_bess.py # Condition prioritization, solar coupled dispatch energy conservation
```

---

## 3. Data Dictionary & Field Specifications

| Field Name | Type | Unit | Physical Range | Missing Value & Validation Policy |
|---|---|---|---|---|
| `timestamp` | ISO-8601 String | UTC / Offset | N/A | Strictly required. Non-chronological or duplicate rows rejected. |
| `panel_id` | String | Dimensionless | N/A | Defaults to asset identifier. |
| `irradiance` | Float | $\text{W/m}^2$ | $0.0 \dots 1500.0$ | Time-aware interpolation for gaps $\le 3$ steps. Clamped to 0 at night. |
| `plane_of_array_irradiance` | Float | $\text{W/m}^2$ | $0.0 \dots 1500.0$ | Transposed from GHI or directly measured. Accounts for panel tilt. |
| `panel_temperature` | Float | $^\circ\text{C}$ | $-40.0 \dots 95.0$ | Back-of-module temperature. Estimated via Sandia model if absent. |
| `ambient_temperature` | Float | $^\circ\text{C}$ | $-40.0 \dots 60.0$ | Dry-bulb ambient air temperature. |
| `voltage` | Float | $\text{V}$ | $0.0 \dots 1500.0$ | DC string operating voltage. Non-zero voltage with zero current flags open breaker. |
| `current` | Float | $\text{A}$ | $0.0 \dots 1000.0$ | DC operating current. Strictly non-negative. |
| `power` | Float | $\text{kW}$ | $0.0 \dots 100,000.0$ | Active generated power. Nighttime generation strictly $0.0\text{ kW}$. |
| `energy` | Float | $\text{kWh}$ | $0.0 \dots 10^9$ | Trapezoidal time integral: $E = \int P dt$. Bounded by max valid dt. |
| `cloud_cover` | Float | Fraction $0 \dots 1$ | $0.0 \dots 1.0$ | Satellite or NWP cloud fraction modulating clear-sky irradiance. |
| `wind_speed` | Float | $\text{m/s}$ | $0.0 \dots 55.0$ | Wind speed driving convective module cooling. |
| `inverter_status` | Enum String | Categorical | Normal, Tripped, Curtailed, Standby | Telemetry bitmask diagnosing inverter trips vs soiling. |
| `sensor_status` | Enum String | Categorical | Normal, Stuck, Out-of-Bounds | Prevents diagnosing telemetry errors as hardware faults. |
| `cleaning_timestamp` | ISO-8601 String | UTC | N/A | Documented panel wash event for soiling step verification. |
| `maintenance_timestamp` | ISO-8601 String | UTC | N/A | Ground-truth log of field maintenance or component replacement. |

---

## 4. API Specification (Mounted on ML Microservice, Port 8231)

All endpoints are hosted directly by the existing Python ML service (`http://127.0.0.1:8231`):

### 1. Health Check
- **Endpoint**: `GET /solar_pv/health`
- **Response**:
```json
{
  "status": "healthy",
  "module": "solar_pv",
  "version": "1.0.0",
  "physics_engine": "IEC 61724 / King Sandia Model",
  "models_available": ["xgboost", "lightgbm", "baseline_persistence"]
}
```

### 2. Generate Reproducible Synthetic Benchmark
- **Endpoint**: `POST /solar_pv/generate-synthetic`
- **Payload**:
```json
{
  "days": 60,
  "include_soiling": true,
  "include_anomalies": true,
  "save_path": "data/datasets/pv_synthetic/pv_synthetic_benchmark.csv"
}
```

### 3. Train PV Forecaster
- **Endpoint**: `POST /solar_pv/forecast/train`
- **Payload**:
```json
{
  "dataset_path": "data/datasets/pv_synthetic/pv_synthetic_benchmark.csv",
  "model_type": "xgboost",
  "n_estimators": 400,
  "learning_rate": 0.04
}
```

### 4. Short-Term Forecast with Uncertainty Intervals
- **Endpoint**: `POST /solar_pv/forecast/predict`
- **Payload**:
```json
{
  "dataset_path": "data/datasets/pv_synthetic/pv_synthetic_benchmark.csv",
  "horizon": 24,
  "model_type": "xgboost"
}
```

### 5. Anomaly Detection & Evidence-Based Root Cause
- **Endpoint**: `POST /solar_pv/anomaly/detect`
- **Query / Body**: `dataset_path` (optional)
- **Response**: List of continuous anomaly events with evidence bundle (`is_weather_explained`, `inverter_status`, `is_stuck_sensor`, `severity`, `confidence`).

### 6. Soiling & Cleaning Recovery Analysis
- **Endpoint**: `POST /solar_pv/soiling/analyze`
- **Query / Body**: `dataset_path` (optional)
- **Response**: Evaluates daily irradiance-weighted Performance Ratio, identifies cleaning recovery steps, calculates daily accumulation rate, and flags missing evidence.

### 7. Long-Term Degradation Analysis
- **Endpoint**: `POST /solar_pv/degradation/analyze`
- **Query / Body**: `dataset_path` (optional)
- **Scientific Sufficiency Gate**: If dataset covers $< 365$ days, returns `INSUFFICIENT_DATA_DURATION` and refuses to publish ungrounded annualized degradation rates. When $\ge 365$ days, calculates Theil-Sen robust slope with 95% confidence intervals.

### 8. Predictive Maintenance Recommendations
- **Endpoint**: `POST /solar_pv/maintenance/recommendations`
- **Query / Body**: `dataset_path` (optional)
- **Response**: Prioritized O&M work orders (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `MONITORING`, `INSUFFICIENT_EVIDENCE`) with engineering inspection guidance.

### 9. Solar-Coupled BESS Dispatch Step
- **Endpoint**: `POST /solar_pv/bess/coupled-dispatch`
- **Payload**:
```json
{
  "solar_power_mw": 50.0,
  "site_load_mw": 10.0,
  "current_soc": 0.50,
  "requested_bess_power_mw": -30.0,
  "interconnection_limit_mw": 100.0,
  "bess_capacity_mwh": 100.0,
  "bess_max_charge_mw": 50.0,
  "bess_max_discharge_mw": 50.0,
  "soc_min": 0.05,
  "soc_max": 0.95,
  "eta_charge": 0.94
}
```

---

## 5. Instructions for Owner: Connecting to Frontend & Rust Backend

### A. Connecting to Rust Control Plane (`backend/`)
The Rust backend already uses `reqwest` to proxy requests to `ml_service_url` (`http://127.0.0.1:8231`).
To integrate Solar PV into the Rust backend:
1. In `backend/src/api/forecast.rs`, add a handler `predict_pv_forecast` that calls `{ml_service_url}/solar_pv/forecast/predict`.
2. In `backend/src/core/backtester.rs`, when evaluating co-located solar + storage, pass `MarketPoint.solar_gen_mw` into the dispatch step to prioritize charging battery from zero-marginal-cost on-site solar before grid import.

### B. Connecting to React Frontend (`frontend/`)
1. Create a service file `frontend/src/services/solarPvService.ts`:
```typescript
import axios from 'axios';

const ML_API = 'http://127.0.0.1:8231/solar_pv';

export const getSolarPvHealth = () => axios.get(`${ML_API}/health`);
export const getPvForecast = (horizon: number = 24) => 
  axios.post(`${ML_API}/forecast/predict`, { horizon, model_type: 'xgboost' });
export const getPvAnomalies = () => axios.post(`${ML_API}/anomaly/detect`);
export const getPvMaintenanceRecs = () => axios.post(`${ML_API}/maintenance/recommendations`);
export const getPvSoiling = () => axios.post(`${ML_API}/soiling/analyze`);
export const getPvDegradation = () => axios.post(`${ML_API}/degradation/analyze`);
```
2. In `frontend/src/components/`, create a `SolarPVPanel.tsx` visual card displaying:
   - 24h Solar Generation Forecast curve with 80% & 95% uncertainty bands.
   - Asset Health Index & Predictive Maintenance Priority alerts.
   - Midday Performance Ratio (PR) & Soiling wash recovery tracking.
