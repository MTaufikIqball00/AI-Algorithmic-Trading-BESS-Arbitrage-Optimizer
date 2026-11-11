"""
FastAPI Router for Solar PV Analytics and BESS Integration.
Designed to be mounted onto the existing Python ML service (Port 8231)
without creating new servers, ports, or processes.
"""
import os
import json
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
import pandas as pd
import numpy as np
from datetime import datetime

from ..config.defaults import PVSystemConfig
from ..data.ingestion.synthetic import SyntheticPVGenerator
from ..data.ingestion.csv_importer import PVCSVImporter
from ..forecasting.xgboost_model import PVXGBoostForecaster
from ..forecasting.lightgbm_model import PVLightGBMForecaster
from ..anomaly_detection.classification import PVAnomalyClassifier
from ..soiling.analysis import SoilingAnalyzer
from ..degradation.analysis import DegradationAnalyzer
from ..maintenance.recommendations import PVMaintenanceAdvisor
from .adapters import BESSIntegrationAdapter
from .bess_contracts import (
    PVForecastPayload,
    BESSCoLocatedDispatchConstraint,
    SolarCoupledDispatchDecision,
    PVSourceType,
    PVDataQualityStatus
)

router = APIRouter(prefix="/solar_pv", tags=["Solar PV Analytics"])

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Global state instances for reuse
system_config = PVSystemConfig()
xgb_forecaster = PVXGBoostForecaster(system_config)
lgb_forecaster = PVLightGBMForecaster(system_config)
anomaly_classifier = PVAnomalyClassifier(system_config)
soiling_analyzer = SoilingAnalyzer(system_config)
degradation_analyzer = DegradationAnalyzer(system_config)
maintenance_advisor = PVMaintenanceAdvisor()
csv_importer = PVCSVImporter()


# Request Schemas
class PVTrainRequest(BaseModel):
    dataset_path: Optional[str] = None
    model_type: str = Field("xgboost", description="'xgboost' or 'lightgbm'")
    n_estimators: int = Field(300, ge=10, le=1000)
    learning_rate: float = Field(0.04, ge=0.001, le=0.5)


class PVPredictRequest(BaseModel):
    dataset_path: Optional[str] = None
    horizon: int = Field(24, ge=1, le=672)
    model_type: str = Field("xgboost", description="'xgboost' or 'lightgbm'")


class PVSyntheticGenerateRequest(BaseModel):
    days: int = Field(60, ge=1, le=730)
    include_soiling: bool = True
    include_anomalies: bool = True
    save_path: Optional[str] = "data/datasets/pv_synthetic/pv_synthetic_benchmark.csv"


class PVCoupledDispatchStepRequest(BaseModel):
    solar_power_mw: float = Field(..., ge=0.0)
    site_load_mw: float = Field(..., ge=0.0)
    current_soc: float = Field(..., ge=0.0, le=1.0)
    requested_bess_power_mw: float = Field(..., description="Negative = charge, Positive = discharge")
    interconnection_limit_mw: float = Field(100.0, ge=1.0)
    bess_capacity_mwh: float = Field(100.0, ge=1.0)
    bess_max_charge_mw: float = Field(50.0, ge=1.0)
    bess_max_discharge_mw: float = Field(50.0, ge=1.0)
    soc_min: float = 0.05
    soc_max: float = 0.95
    eta_charge: float = 0.94


def _resolve_repo_file(rel_or_abs: str) -> Optional[str]:
    for cand in [rel_or_abs, os.path.join(_REPO_ROOT, rel_or_abs), os.path.join("..", rel_or_abs)]:
        if cand and os.path.exists(cand):
            return os.path.abspath(cand)
    return None


def _resolve_pv_dataset(path: Optional[str] = None) -> str:
    """Resolve PV dataset with fallbacks across CWD and repo root."""
    if path:
        found = _resolve_repo_file(path)
        if found:
            return found

    candidates = [
        "data/datasets/kaggle_solar/plant_1_aggregate.csv",
        "data/datasets/pv_synthetic/pv_synthetic_benchmark.csv",
        "data/datasets/pv_real/nrel_pvdaq_sample.csv",
        "data/datasets/active_market_dataset.csv",
        "data/datasets/caiso_hourly_benchmark_2024.csv"
    ]
    for c in candidates:
        found = _resolve_repo_file(c)
        if found:
            return found

    # If none exists, auto-generate synthetic benchmark
    syn_dir = os.path.join(_REPO_ROOT, "data", "datasets", "pv_synthetic")
    os.makedirs(syn_dir, exist_ok=True)
    syn_path = os.path.join(syn_dir, "pv_synthetic_benchmark.csv")
    gen = SyntheticPVGenerator()
    df_syn = gen.generate(days=60)
    df_syn.to_csv(syn_path, index=False)
    return os.path.abspath(syn_path)


def _build_calibrated_config(df: pd.DataFrame, default_id: str = "Gandikota_Plant_1") -> PVSystemConfig:
    """Dynamically calibrate PVSystemConfig capacity to the scale of the dataset."""
    p_series = None
    if "power" in df.columns:
        p_series = pd.to_numeric(df["power"], errors="coerce")
    elif "solar_gen_mw" in df.columns:
        p_series = pd.to_numeric(df["solar_gen_mw"], errors="coerce") * 1000.0

    peak_ac_kw = float(p_series.max()) if p_series is not None and not p_series.dropna().empty else 1000.0
    if peak_ac_kw <= 0 or np.isnan(peak_ac_kw):
        peak_ac_kw = 1000.0

    dc_Series = pd.to_numeric(df["dc_power"], errors="coerce") if "dc_power" in df.columns else None
    peak_dc_kw = float(dc_Series.max()) * 1.03 if dc_Series is not None and not dc_Series.dropna().empty else peak_ac_kw * 1.08

    panel_id = str(df["panel_id"].iloc[0]) if "panel_id" in df.columns and len(df) > 0 else default_id
    is_india = "gandikota" in panel_id.lower() or peak_ac_kw > 15000.0
    return PVSystemConfig(
        system_id=panel_id,
        rated_dc_power_kw=round(peak_dc_kw, 2),
        inverter_ac_power_kw=round(peak_ac_kw * 1.02, 2),
        latitude=14.815 if is_india else system_config.latitude,
        longitude=78.285 if is_india else system_config.longitude,
        panel_tilt_deg=15.0 if is_india else system_config.panel_tilt_deg,
        panel_azimuth_deg=180.0
    )


def _resolve_model_dir(dataset_path: str) -> str:
    if "kaggle_solar" in dataset_path.replace("\\", "/"):
        cand = _resolve_repo_file("data/models/kaggle_solar")
        if cand:
            return cand
        return os.path.join(_REPO_ROOT, "data", "models", "kaggle_solar")
    cand = _resolve_repo_file("data/models/solar_pv")
    if cand:
        return cand
    return os.path.join(_REPO_ROOT, "data", "models", "solar_pv")


@router.get("/health")
def solar_pv_health():
    return {
        "status": "healthy",
        "module": "solar_pv",
        "version": "1.0.0",
        "physics_engine": "IEC 61724 / King Sandia Model",
        "models_available": ["xgboost", "lightgbm", "baseline_persistence"]
    }


@router.post("/generate-synthetic")
def generate_synthetic(req: PVSyntheticGenerateRequest):
    try:
        gen = SyntheticPVGenerator(system_config)
        df_syn = gen.generate(
            days=req.days,
            include_soiling_cycle=req.include_soiling,
            include_anomalies=req.include_anomalies
        )
        if req.save_path:
            os.makedirs(os.path.dirname(req.save_path), exist_ok=True)
            df_syn.to_csv(req.save_path, index=False)

        return {
            "status": "success",
            "message": f"Generated {len(df_syn)} synthetic PV records ({req.days} days).",
            "saved_to": req.save_path,
            "provenance": "SYNTHETIC_SIMULATED",
            "sample_columns": df_syn.columns.tolist()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forecast/train")
def train_pv_forecast(req: PVTrainRequest):
    path = _resolve_pv_dataset(req.dataset_path)
    try:
        df = pd.read_csv(path)
        if "power" not in df.columns and "solar_gen_mw" in df.columns:
            df["power"] = pd.to_numeric(df["solar_gen_mw"], errors="coerce") * 1000.0
        cfg = _build_calibrated_config(df)
        m_dir = _resolve_model_dir(path)
        target_col = "power"
        if req.model_type.lower() == "lightgbm":
            forecaster = PVLightGBMForecaster(cfg, model_dir=m_dir)
            meta = forecaster.train(df, target_col=target_col, n_estimators=req.n_estimators, learning_rate=req.learning_rate)
        else:
            forecaster = PVXGBoostForecaster(cfg, model_dir=m_dir)
            meta = forecaster.train(df, target_col=target_col, n_estimators=req.n_estimators, learning_rate=req.learning_rate)

        return {
            "status": "success",
            "model_type": req.model_type,
            "metrics": meta.get("metrics"),
            "improvement_pct": meta.get("improvement_over_baseline_pct"),
            "baseline_comparisons": meta.get("baseline_comparisons")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/forecast/predict")
def predict_pv_forecast(req: PVPredictRequest):
    path = _resolve_pv_dataset(req.dataset_path)
    try:
        df = pd.read_csv(path)
        if "power" not in df.columns and "solar_gen_mw" in df.columns:
            df["power"] = pd.to_numeric(df["solar_gen_mw"], errors="coerce") * 1000.0
        cfg = _build_calibrated_config(df)
        m_dir = _resolve_model_dir(path)

        # If dataset is 15-minute resolution and user requests default 24h (24), scale to 96 steps (24 hours)
        horizon = req.horizon
        if "timestamp" in df.columns and len(df) > 2:
            ts = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            med_sec = float(ts.diff().dt.total_seconds().dropna().median() or 3600.0)
            if 800 <= med_sec <= 1000 and horizon == 24:
                horizon = 96

        if req.model_type.lower() == "lightgbm":
            forecaster = PVLightGBMForecaster(cfg, model_dir=m_dir)
            try:
                preds = forecaster.predict(df, horizon=horizon)
            except RuntimeError:
                forecaster.train(df, target_col="power")
                preds = forecaster.predict(df, horizon=horizon)
        else:
            forecaster = PVXGBoostForecaster(cfg, model_dir=m_dir)
            try:
                preds = forecaster.predict(df, horizon=horizon)
            except RuntimeError:
                forecaster.train(df, target_col="power")
                preds = forecaster.predict(df, horizon=horizon)

        payload = BESSIntegrationAdapter.format_forecast_payload(
            predictions=preds,
            site_id=cfg.system_id,
            source_type=PVSourceType.SYNTHETIC_SIMULATED if "synthetic" in path.lower() else PVSourceType.REAL_HISTORICAL,
            data_quality=PVDataQualityStatus.SYNTHETIC if "synthetic" in path.lower() else PVDataQualityStatus.VERIFIED
        )
        return payload.model_dump() if hasattr(payload, "model_dump") else payload.dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _run_inverter_aware_anomaly_scan(path: str, df: pd.DataFrame, cfg: PVSystemConfig, explicit_path: Optional[str]):
    """
    If running on the default aggregate plant dataset and the companion inverter-level CSV exists,
    evaluate sample inverters with per-inverter capacity calibration so individual inverter trip
    events are not masked by the 22-inverter aggregate sum.
    """
    inv_path = _resolve_repo_file("data/datasets/kaggle_solar/plant_1_inverters.csv")
    if explicit_path is None and inv_path and "plant_1_aggregate" in path.replace("\\", "/"):
        try:
            df_inv_all = pd.read_csv(inv_path)
            sample_invs = df_inv_all["panel_id"].unique()[:3]
            all_events = []
            for inv_id in sample_invs:
                df_sub = df_inv_all[df_inv_all["panel_id"] == inv_id].copy().reset_index(drop=True)
                inv_cfg = _build_calibrated_config(df_sub, default_id=str(inv_id))
                clf = PVAnomalyClassifier(inv_cfg)
                ev, _ = clf.classify_dataset(df_sub, asset_id=str(inv_id))
                all_events.extend(ev)
            if all_events:
                return all_events
        except Exception:
            pass

    classifier = PVAnomalyClassifier(cfg)
    events, _ = classifier.classify_dataset(df, asset_id=cfg.system_id)
    return events


@router.post("/anomaly/detect")
def detect_anomalies(dataset_path: Optional[str] = None):
    path = _resolve_pv_dataset(dataset_path)
    try:
        df = pd.read_csv(path)
        if "power" not in df.columns and "solar_gen_mw" in df.columns:
            df["power"] = pd.to_numeric(df["solar_gen_mw"], errors="coerce") * 1000.0
        cfg = _build_calibrated_config(df)
        events = _run_inverter_aware_anomaly_scan(path, df, cfg, dataset_path)
        return {
            "status": "success",
            "asset_id": cfg.system_id,
            "total_anomalies_detected": len(events),
            "events": [e.to_dict() for e in events]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/soiling/analyze")
def analyze_soiling(dataset_path: Optional[str] = None):
    path = _resolve_pv_dataset(dataset_path)
    try:
        df = pd.read_csv(path)
        if "power" not in df.columns and "solar_gen_mw" in df.columns:
            df["power"] = pd.to_numeric(df["solar_gen_mw"], errors="coerce") * 1000.0
        cfg = _build_calibrated_config(df)
        analyzer = SoilingAnalyzer(cfg)
        result = analyzer.analyze_soiling(df)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/degradation/analyze")
def analyze_degradation(dataset_path: Optional[str] = None):
    path = _resolve_pv_dataset(dataset_path)
    try:
        df = pd.read_csv(path)
        if "power" not in df.columns and "solar_gen_mw" in df.columns:
            df["power"] = pd.to_numeric(df["solar_gen_mw"], errors="coerce") * 1000.0
        cfg = _build_calibrated_config(df)
        analyzer = DegradationAnalyzer(cfg)
        target_col = "power" if "power" in df.columns else "solar_gen_mw"
        result = analyzer.analyze_degradation(df, target_col=target_col)
        return result.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/maintenance/recommendations")
def get_maintenance_recommendations(dataset_path: Optional[str] = None):
    path = _resolve_pv_dataset(dataset_path)
    try:
        df = pd.read_csv(path)
        if "power" not in df.columns and "solar_gen_mw" in df.columns:
            df["power"] = pd.to_numeric(df["solar_gen_mw"], errors="coerce") * 1000.0
        cfg = _build_calibrated_config(df)
        events = _run_inverter_aware_anomaly_scan(path, df, cfg, dataset_path)
        recs = maintenance_advisor.generate_recommendations(
            asset_id=cfg.system_id,
            events=events,
            analysis_period="34-Day Historical Observation Window",
            missing_data_fields=[c for c in ["voltage", "current", "cleaning_timestamp"] if c not in df.columns]
        )
        return {
            "status": "success",
            "asset_id": cfg.system_id,
            "recommendation_count": len(recs),
            "recommendations": [r.to_dict() for r in recs]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/bess/coupled-dispatch")
def coupled_dispatch_step(req: PVCoupledDispatchStepRequest):
    constraints = BESSCoLocatedDispatchConstraint(
        site_interconnection_limit_mw=req.interconnection_limit_mw,
        bess_max_charge_mw=req.bess_max_charge_mw,
        bess_max_discharge_mw=req.bess_max_discharge_mw,
        bess_capacity_mwh=req.bess_capacity_mwh,
        soc_min=req.soc_min,
        soc_max=req.soc_max,
        eta_charge=req.eta_charge
    )
    decision = BESSIntegrationAdapter.dispatch_coupled_solar_step(
        solar_power_mw=req.solar_power_mw,
        site_load_mw=req.site_load_mw,
        current_soc=req.current_soc,
        requested_bess_power_mw=req.requested_bess_power_mw,
        constraints=constraints,
        timestamp=datetime.utcnow().isoformat() + "Z"
    )
    return decision.model_dump() if hasattr(decision, "model_dump") else decision.dict()


@router.get("/summary")
def get_solar_pv_dashboard_summary(model_type: str = Query("xgboost")):
    """
    Comprehensive dashboard summary endpoint uniting real dataset telemetry,
    forecasting, model evaluation metrics, soiling, degradation, anomalies,
    predictive maintenance, and co-located BESS dispatch.
    """
    path = _resolve_pv_dataset(None)
    try:
        df = pd.read_csv(path)
        if "power" not in df.columns and "solar_gen_mw" in df.columns:
            df["power"] = pd.to_numeric(df["solar_gen_mw"], errors="coerce") * 1000.0
        cfg = _build_calibrated_config(df)
        m_dir = _resolve_model_dir(path)

        # Load archive summary if present
        archive_summary = {}
        arch_path = _resolve_repo_file("data/datasets/kaggle_solar/archive_processing_summary.json")
        if arch_path and os.path.exists(arch_path):
            with open(arch_path, "r") as f:
                archive_summary = json.load(f)

        # Load model metadata
        xgb_meta = {}
        lgb_meta = {}
        xgb_meta_path = os.path.join(m_dir, "solar_xgb_metadata.json")
        lgb_meta_path = os.path.join(m_dir, "solar_lgb_metadata.json")
        if os.path.exists(xgb_meta_path):
            with open(xgb_meta_path, "r") as f:
                xgb_meta = json.load(f)
        if os.path.exists(lgb_meta_path):
            with open(lgb_meta_path, "r") as f:
                lgb_meta = json.load(f)

        # 24h forecast
        forecast_payload = predict_pv_forecast(PVPredictRequest(dataset_path=path, horizon=24, model_type=model_type))

        # Soiling & Degradation
        soiling_res = SoilingAnalyzer(cfg).analyze_soiling(df).to_dict()
        deg_res = DegradationAnalyzer(cfg).analyze_degradation(df, target_col="power").to_dict()

        # Anomalies & Maintenance Recommendations
        events = _run_inverter_aware_anomaly_scan(path, df, cfg, None)
        recs = maintenance_advisor.generate_recommendations(
            asset_id=cfg.system_id,
            events=events,
            analysis_period="34-Day Historical Observation Window",
            missing_data_fields=[c for c in ["voltage", "current", "cleaning_timestamp"] if c not in df.columns]
        )

        # Sample midday coupled BESS dispatch
        peak_mw = round(float(df["power"].max()) / 1000.0, 2) if "power" in df.columns else 23.72
        sample_solar_mw = round(min(peak_mw * 0.82, 23.72), 2) if peak_mw > 5.0 else 5.0
        coupled_example = coupled_dispatch_step(PVCoupledDispatchStepRequest(
            solar_power_mw=sample_solar_mw,
            site_load_mw=5.0,
            current_soc=0.30,
            requested_bess_power_mw=-12.0,
            interconnection_limit_mw=25.0,
            bess_capacity_mwh=40.0,
            bess_max_charge_mw=12.0,
            bess_max_discharge_mw=12.0
        ))

        return {
            "status": "success",
            "asset_id": cfg.system_id,
            "dataset_path": path,
            "rated_dc_kw": cfg.rated_dc_power_kw,
            "rated_ac_kw": cfg.inverter_ac_power_kw,
            "total_intervals": len(df),
            "archive_summary": archive_summary,
            "xgboost_metadata": xgb_meta,
            "lightgbm_metadata": lgb_meta,
            "forecast": forecast_payload,
            "soiling": soiling_res,
            "degradation": deg_res,
            "anomaly_summary": {
                "total_detected": len(events),
                "events": [e.to_dict() for e in events[:25]]
            },
            "maintenance": {
                "recommendation_count": len(recs),
                "recommendations": [r.to_dict() for r in recs]
            },
            "coupled_dispatch_example": coupled_example
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


