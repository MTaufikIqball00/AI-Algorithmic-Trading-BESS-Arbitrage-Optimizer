"""
Tests for PV Data Validation Engine.
Validates timestamp ordering, duplicate detection, physical bounds, and quality metrics.
"""
import pytest
import pandas as pd
import numpy as np

from solar_pv.data.validation.validator import PVDataValidator
from solar_pv.data.dictionary import DataQualityFlag


def test_validator_detects_non_chronological():
    validator = PVDataValidator()
    df = pd.DataFrame({
        "timestamp": ["2024-01-01T02:00:00Z", "2024-01-01T01:00:00Z", "2024-01-01T03:00:00Z"],
        "power": [10.0, 5.0, 15.0]
    })
    is_valid, report, issues = validator.validate(df)
    assert not report.is_chronological
    assert any("not monotonically increasing" in issue for issue in issues)


def test_validator_detects_duplicate_timestamps():
    validator = PVDataValidator()
    df = pd.DataFrame({
        "timestamp": ["2024-01-01T01:00:00Z", "2024-01-01T01:00:00Z", "2024-01-01T02:00:00Z"],
        "power": [5.0, 5.0, 10.0]
    })
    is_valid, report, issues = validator.validate(df)
    assert report.duplicate_timestamps == 1
    assert any("duplicate" in issue for issue in issues)


def test_validator_detects_out_of_bounds_physical_values():
    validator = PVDataValidator()
    df = pd.DataFrame({
        "timestamp": ["2024-01-01T12:00:00Z", "2024-01-01T13:00:00Z"],
        "irradiance": [900.0, 1850.0], # 1850 is impossible (> 1500 max)
        "ambient_temperature": [25.0, 75.0], # 75 C is impossible outdoor ambient (> 60 max)
        "power": [400.0, 500.0]
    })
    is_valid, report, issues = validator.validate(df)
    assert report.field_out_of_bounds_counts["irradiance"] == 1
    assert report.field_out_of_bounds_counts["ambient_temperature"] == 1


def test_validator_computes_quality_score():
    validator = PVDataValidator()
    # Perfect dataset
    df_good = pd.DataFrame({
        "timestamp": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z", "2024-01-01T02:00:00Z"],
        "power": [0.0, 0.0, 0.0],
        "irradiance": [0.0, 0.0, 0.0]
    })
    is_valid, report, _ = validator.validate(df_good)
    assert is_valid
    assert report.quality_score >= 90.0
    assert report.completeness_pct == 100.0
