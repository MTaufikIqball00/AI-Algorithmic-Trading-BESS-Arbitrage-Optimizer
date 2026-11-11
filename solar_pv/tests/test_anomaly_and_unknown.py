"""
Tests for Anomaly Detection and Evidence-Based Classification.
Verifies root-cause separation and strict UNKNOWN_NEEDS_INVESTIGATION enforcement.
"""
import pytest
import pandas as pd
import numpy as np

from solar_pv.data.ingestion.synthetic import SyntheticPVGenerator
from solar_pv.anomaly_detection.detection import PVAnomalyDetector
from solar_pv.anomaly_detection.classification import PVAnomalyClassifier
from solar_pv.anomaly_detection.evidence import AnomalyClassification, AnomalySeverity
from solar_pv.config.defaults import PVSystemConfig


@pytest.fixture(scope="module")
def anomaly_pv_data():
    gen = SyntheticPVGenerator(seed=42)
    # Generate 30 days containing injected inverter trip and stuck sensor anomalies
    return gen.generate(days=30, include_anomalies=True)


def test_nighttime_zero_not_flagged_as_anomaly(anomaly_pv_data):
    detector = PVAnomalyDetector()
    df_res = detector.compute_residuals(anomaly_pv_data)

    # Nighttime rows: where solar_elevation is <= 0 or POA < 20
    night_mask = ~df_res["is_daylight"]
    # All residuals during night should be 0.0 kW
    assert (df_res.loc[night_mask, "residual_kw"] == 0.0).all()


def test_hardware_trip_anomaly_detection(anomaly_pv_data):
    classifier = PVAnomalyClassifier()
    events, df_res = classifier.classify_dataset(anomaly_pv_data)

    hw_events = [e for e in events if e.classification == AnomalyClassification.POTENTIAL_EQUIPMENT_FAULT]
    assert len(hw_events) > 0
    # Verify severity and confidence
    for e in hw_events:
        assert e.severity in [AnomalySeverity.CRITICAL, AnomalySeverity.HIGH]
        assert e.confidence is not None and e.confidence > 0.85
        assert e.expected_power_kw > e.actual_power_kw


def test_sensor_fault_classification():
    config = PVSystemConfig(rated_dc_power_kw=1000.0)
    classifier = PVAnomalyClassifier(config)

    # Create synthetic series where sensor flatlines
    timestamps = [f"2024-06-01T{h:02d}:00:00Z" for h in range(10, 18)]
    df = pd.DataFrame({
        "timestamp": timestamps,
        "power": [450.0] * 8, # completely flatlined
        "plane_of_array_irradiance": [500.0, 700.0, 950.0, 920.0, 800.0, 600.0, 400.0, 200.0],
        "inverter_status": ["OPERATING_NORMAL"] * 8,
        "sensor_status": ["STUCK"] * 8,
        "panel_temperature": [45.0] * 8,
        "cloud_cover": [0.0] * 8
    })

    events, _ = classifier.classify_dataset(df)
    assert len(events) > 0
    assert any(e.classification == AnomalyClassification.SENSOR_FAULT for e in events)


def test_insufficient_evidence_yields_unknown():
    config = PVSystemConfig(rated_dc_power_kw=1000.0)
    classifier = PVAnomalyClassifier(config)

    # Moderate unexplained drop (actual ~300 kW vs expected ~580 kW at 600 W/m^2, ratio ~0.51)
    # with moderate clouds (0.50), no inverter fault code, no cleaning log, and no current telemetry
    timestamps = [f"2024-06-01T{h:02d}:00:00Z" for h in range(11, 14)]
    df = pd.DataFrame({
        "timestamp": timestamps,
        "power": [300.0, 310.0, 290.0],
        "plane_of_array_irradiance": [600.0, 620.0, 580.0],
        "cloud_cover": [0.50, 0.50, 0.50],
        "inverter_status": ["UNKNOWN"] * 3,
        "sensor_status": ["UNKNOWN"] * 3
    })

    events, _ = classifier.classify_dataset(df)
    assert len(events) == 1
    assert events[0].classification == AnomalyClassification.UNKNOWN_NEEDS_INVESTIGATION
    assert events[0].severity == AnomalySeverity.INSUFFICIENT_EVIDENCE
    assert events[0].confidence is None # strictly uncalibrated when evidence is insufficient

