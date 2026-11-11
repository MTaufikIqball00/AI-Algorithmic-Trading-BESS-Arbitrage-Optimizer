"""
Integration tests for Solar PV endpoints in FastAPI ML service.
"""
import pytest
from fastapi.testclient import TestClient
import os
import sys

# Ensure ml_service and repo root are in path
ml_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
repo_dir = os.path.dirname(ml_dir)
if ml_dir not in sys.path:
    sys.path.insert(0, ml_dir)
if repo_dir not in sys.path:
    sys.path.insert(0, repo_dir)

from service import app

client = TestClient(app)


def test_solar_pv_health_endpoint():
    resp = client.get("/solar_pv/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["module"] == "solar_pv"


def test_solar_pv_generate_synthetic_endpoint(tmp_path):
    target_csv = str(tmp_path / "test_syn.csv")
    resp = client.post("/solar_pv/generate-synthetic", json={
        "days": 5,
        "include_soiling": False,
        "include_anomalies": False,
        "save_path": target_csv
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert os.path.exists(target_csv)


def test_solar_pv_coupled_dispatch_endpoint():
    resp = client.post("/solar_pv/bess/coupled-dispatch", json={
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
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["solar_available_mw"] == 50.0
    assert data["solar_to_load_mw"] == 10.0
    assert data["solar_to_bess_charge_mw"] > 0.0
    assert not data["constraint_violated"]


def test_solar_pv_summary_endpoint():
    resp = client.get("/solar_pv/summary?model_type=xgboost")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert "forecast" in data
    assert "soiling" in data
    assert "degradation" in data
    assert "maintenance" in data
    assert "coupled_dispatch_example" in data

