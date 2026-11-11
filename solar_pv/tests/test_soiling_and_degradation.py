"""
Tests for Soiling and Long-Term Degradation Analysis.
Verifies evidence sufficiency gates, cleaning step calculations, and strict 365-day threshold for annualized degradation.
"""
import pytest
import pandas as pd
import numpy as np

from solar_pv.data.ingestion.synthetic import SyntheticPVGenerator
from solar_pv.soiling.analysis import SoilingAnalyzer
from solar_pv.degradation.analysis import DegradationAnalyzer


def test_soiling_analysis_with_cleaning_log():
    gen = SyntheticPVGenerator(seed=42)
    # Generate 40 days containing simulated dry soiling and cleaning event
    df_soiled = gen.generate(days=40, include_soiling_cycle=True)

    analyzer = SoilingAnalyzer()
    res = analyzer.analyze_soiling(df_soiled)

    assert res.analyzed_days >= 7
    # Since cleaning event exists on day 35, wash recovery step should be evaluated
    assert res.cleaning_events_detected >= 1
    assert res.status in ["CONFIRMED_SOILING", "POTENTIAL_SOILING"]
    assert res.wash_recovery_pct is not None


def test_soiling_analysis_without_cleaning_log_reports_missing_evidence():
    gen = SyntheticPVGenerator(seed=42)
    df = gen.generate(days=20, include_soiling_cycle=False)
    # Strip cleaning column
    df["cleaning_timestamp"] = None

    analyzer = SoilingAnalyzer()
    res = analyzer.analyze_soiling(df)

    # Must NOT report confirmed soiling
    assert res.status != "CONFIRMED_SOILING"
    assert len(res.missing_evidence) > 0


def test_degradation_insufficient_duration_gate():
    # If data duration < 365 days, analyzer must refuse to publish an annualized degradation rate!
    gen = SyntheticPVGenerator(seed=42)
    df_short = gen.generate(days=90) # 90 days < 365 days

    analyzer = DegradationAnalyzer()
    res = analyzer.analyze_degradation(df_short)

    assert res.status == "INSUFFICIENT_DATA_DURATION"
    assert not res.is_statistically_defensible
    assert res.annualized_degradation_pct_year is None
    assert res.confidence_interval_95 is None
    assert "conflates seasonal solar zenith/temperature variations" in res.scientific_warning


def test_degradation_sufficient_multiyear_analysis():
    # Generate 400 days (spans full seasonal cycle)
    # To keep test fast, generate daily midday points
    dates = pd.date_range("2022-01-01", periods=400, freq="D", tz="UTC")
    # True degradation rate = 0.5% per year
    t_years = np.arange(400) / 365.25
    base_power = 900.0 * (1.0 - 0.005 * t_years) + np.random.normal(0, 5, size=400)

    df_multiyear = pd.DataFrame({
        "timestamp": [d.isoformat() for d in dates],
        "power": base_power,
        "plane_of_array_irradiance": [800.0] * 400,
        "panel_temperature": [45.0] * 400,
        "ambient_temperature": [25.0] * 400
    })

    analyzer = DegradationAnalyzer()
    res = analyzer.analyze_degradation(df_multiyear)

    assert res.status == "SUFFICIENT_DATA_VALIDATED"
    assert res.is_statistically_defensible
    assert res.annualized_degradation_pct_year is not None
    assert res.confidence_interval_95 is not None
    # Estimated rate should be approximately 0.5% (+/- 0.3%)
    assert abs(res.annualized_degradation_pct_year - 0.5) < 0.4
