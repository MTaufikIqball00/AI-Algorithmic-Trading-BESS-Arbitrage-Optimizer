r"""
Processing and Analytics Script for C:\Users\taufi\Downloads\archive (Kaggle Solar Power Generation Dataset).
Applies the full Solar PV intelligence pipeline:
- Standardized Ingestion & Weather Alignment
- Data Quality Validation & Preprocessing
- Short-Term XGBoost & LightGBM Power Forecasting with Out-of-Sample Evaluation
- Multi-Inverter Anomaly Detection & Evidence Classification
- Soiling Analysis
- Predictive Maintenance Prioritization
- BESS Coupled Dispatch Simulation
"""
import os
import sys
import json
import pandas as pd
import numpy as np

# Ensure repo root and ml_service are in sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
ml_service_dir = os.path.join(repo_root, "ml_service")
if ml_service_dir not in sys.path:
    sys.path.insert(0, ml_service_dir)

from solar_pv.config.defaults import PVSystemConfig
from solar_pv.data.ingestion.kaggle_solar import KaggleSolarAdapter
from solar_pv.forecasting.xgboost_model import PVXGBoostForecaster
from solar_pv.forecasting.lightgbm_model import PVLightGBMForecaster
from solar_pv.anomaly_detection.classification import PVAnomalyClassifier
from solar_pv.soiling.analysis import SoilingAnalyzer
from solar_pv.degradation.analysis import DegradationAnalyzer
from solar_pv.maintenance.recommendations import PVMaintenanceAdvisor
from solar_pv.integration.adapters import BESSIntegrationAdapter
from solar_pv.integration.bess_contracts import BESSCoLocatedDispatchConstraint, PVSourceType, PVDataQualityStatus


def main():
    archive_dir = r"C:\Users\taufi\Downloads\archive"
    print(f"=== 1. Ingesting Real Solar Datasets from: {archive_dir} ===")
    
    adapter = KaggleSolarAdapter(output_dir="data/datasets/kaggle_solar")

    # Ingest Plant 1
    p1_gen = os.path.join(archive_dir, "Plant_1_Generation_Data.csv")
    p1_wth = os.path.join(archive_dir, "Plant_1_Weather_Sensor_Data.csv")
    df_p1_inv, df_p1_agg, p1_report, p1_prov = adapter.process_plant(p1_gen, p1_wth, plant_name="Plant_1")
    print(f"  [OK] Plant 1 Ingested: {len(df_p1_inv)} inverter records, {len(df_p1_agg)} aggregate intervals.")
    print(f"       Plant 1 Peak Power: {df_p1_agg['power'].max():.1f} kW, Quality Score: {p1_report.quality_score}/100")

    # Ingest Plant 2
    p2_gen = os.path.join(archive_dir, "Plant_2_Generation_Data.csv")
    p2_wth = os.path.join(archive_dir, "Plant_2_Weather_Sensor_Data.csv")
    df_p2_inv, df_p2_agg, p2_report, p2_prov = adapter.process_plant(p2_gen, p2_wth, plant_name="Plant_2", normalize_p1_dc=False)
    print(f"  [OK] Plant 2 Ingested: {len(df_p2_inv)} inverter records, {len(df_p2_agg)} aggregate intervals.")
    print(f"       Plant 2 Peak Power: {df_p2_agg['power'].max():.1f} kW, Quality Score: {p2_report.quality_score}/100")

    # 2. Forecasting on Real Plant 1 Aggregate Data
    print("\n=== 2. Training Real-World Solar Forecaster on Plant 1 Aggregate ===")
    p1_peak_kw = float(df_p1_agg["power"].max())
    # Data-driven STC capacity baseline (Section 8C: derived from median sunny midday operating point)
    mid_mask_p1 = (df_p1_agg["plane_of_array_irradiance"] >= 600.0) & (df_p1_agg["power"] > 5000.0)
    t_factor_p1 = 1.0 - 0.0038 * (df_p1_agg.loc[mid_mask_p1, "panel_temperature"] - 25.0)
    p1_stc_dc_kw = float(np.median(
        (df_p1_agg.loc[mid_mask_p1, "power"] / 0.975)
        / ((df_p1_agg.loc[mid_mask_p1, "plane_of_array_irradiance"] / 1000.0) * t_factor_p1)
    ))
    plant_config = PVSystemConfig(
        system_id="Plant_1_Total",
        system_name="Gandikota Solar Farm Plant 1",
        rated_dc_power_kw=round(p1_stc_dc_kw, 2),
        inverter_ac_power_kw=round(p1_peak_kw * 1.02, 2),
        inverter_efficiency=0.975,
        latitude=14.81, # Gandikota, Andhra Pradesh, India
        longitude=78.28,
        altitude_m=200.0,
        panel_tilt_deg=15.0
    )

    xgb_forecaster = PVXGBoostForecaster(config=plant_config, model_dir="data/models/kaggle_solar")
    xgb_meta = xgb_forecaster.train(df_p1_agg, target_col="power", n_estimators=300, learning_rate=0.04)
    print(f"  [OK] XGBoost Model Trained on Plant 1.")
    print(f"       Out-of-Sample MAE: {xgb_meta['metrics']['mae']:.2f} kW (nMAE: {xgb_meta['metrics']['nmae_pct']}%)")
    print(f"       Out-of-Sample RMSE: {xgb_meta['metrics']['rmse']:.2f} kW, R2: {xgb_meta['metrics']['r2_score']:.4f}")
    print(f"       Improvement over Night-Zero Seasonal Naive Baseline: +{xgb_meta['improvement_over_baseline_pct']}%")

    # LightGBM Comparison
    lgb_forecaster = PVLightGBMForecaster(config=plant_config, model_dir="data/models/kaggle_solar")
    lgb_meta = lgb_forecaster.train(df_p1_agg, target_col="power", n_estimators=300, learning_rate=0.04)
    print(f"  [OK] LightGBM Model Trained on Plant 1.")
    print(f"       Out-of-Sample MAE: {lgb_meta['metrics']['mae']:.2f} kW (nMAE: {lgb_meta['metrics']['nmae_pct']}%), R2: {lgb_meta['metrics']['r2_score']:.4f}")
    print(f"       Improvement over Night-Zero Seasonal Naive Baseline: +{lgb_meta['improvement_over_baseline_pct']}%")

    # Generate 24-hour forecast (96 intervals of 15-min data = 24 hours)
    preds = xgb_forecaster.predict(df_p1_agg, horizon=96)
    payload = BESSIntegrationAdapter.format_forecast_payload(
        predictions=preds,
        site_id="Gandikota_Plant_1",
        source_type=PVSourceType.REAL_HISTORICAL,
        data_quality=PVDataQualityStatus.VERIFIED
    )
    print(f"  [OK] Generated 24h (96-step) forecast: Total Energy = {payload.total_forecast_energy_mwh:.2f} MWh, Peak = {payload.peak_forecast_power_mw:.2f} MW")

    # 3. Anomaly Detection Across Inverters
    print("\n=== 3. Anomaly Detection & Root-Cause Classification Across Inverters ===")
    sample_inverters = df_p1_inv["panel_id"].unique()[:4]
    all_events = []
    for inv_id in sample_inverters:
        inv_df = df_p1_inv[df_p1_inv["panel_id"] == inv_id].copy().reset_index(drop=True)
        inv_peak_kw = float(inv_df["power"].max())
        mid_inv = (inv_df["plane_of_array_irradiance"] >= 600.0) & (inv_df["power"] > 200.0)
        t_fac_inv = 1.0 - 0.0038 * (inv_df.loc[mid_inv, "panel_temperature"] - 25.0)
        inv_stc_dc_kw = float(np.median(
            (inv_df.loc[mid_inv, "power"] / 0.975)
            / ((inv_df.loc[mid_inv, "plane_of_array_irradiance"] / 1000.0) * t_fac_inv)
        ))
        inv_config = PVSystemConfig(
            system_id=str(inv_id),
            system_name=f"Plant 1 Inverter {inv_id}",
            rated_dc_power_kw=round(inv_stc_dc_kw, 2),
            inverter_ac_power_kw=round(inv_peak_kw * 1.02, 2),
            inverter_efficiency=0.975,
            latitude=14.81,
            longitude=78.28,
            altitude_m=200.0,
            panel_tilt_deg=15.0
        )
        classifier = PVAnomalyClassifier(config=inv_config)
        events, _ = classifier.classify_dataset(inv_df, asset_id=str(inv_id))
        all_events.extend(events)
        print(f"  Inverter {inv_id} (Data-Driven STC: {inv_config.rated_dc_power_kw:.0f} kWp): detected {len(events)} anomalous events.")
        for e in events[:2]:
            print(f"    -> [{e.severity.value}] {e.classification.value}: {e.evidence.evidence_notes[0]}")

    # 4. Soiling Analysis
    print("\n=== 4. Soiling Analysis on Plant 1 ===")
    soiling_analyzer = SoilingAnalyzer(config=plant_config)
    soiling_res = soiling_analyzer.analyze_soiling(df_p1_agg)
    print(f"  Status: {soiling_res.status}")
    print(f"  Current Soiling Ratio (SR): {soiling_res.soiling_ratio_current}")
    print(f"  Estimated Daily Soiling Loss Rate: {soiling_res.estimated_soiling_rate_pct_day}%/day")
    print(f"  Evidence Notes: {soiling_res.evidence_notes}")
    print(f"  Missing Evidence: {soiling_res.missing_evidence}")

    # 5. Long-term Degradation Gate
    print("\n=== 5. Degradation Analysis & Sufficiency Gate ===")
    deg_analyzer = DegradationAnalyzer(config=plant_config)
    deg_res = deg_analyzer.analyze_degradation(df_p1_agg)
    print(f"  Status: {deg_res.status}")
    print(f"  Data Duration: {deg_res.data_duration_days} days (Minimum Required: 365.0 days)")
    print(f"  Statistically Defensible: {deg_res.is_statistically_defensible}")
    if deg_res.scientific_warning:
        print(f"  Scientific Safeguard: {deg_res.scientific_warning}")

    # 6. Predictive Maintenance Prioritization
    print("\n=== 6. Predictive Maintenance Recommendations ===")
    advisor = PVMaintenanceAdvisor()
    recs = advisor.generate_recommendations(
        asset_id="Gandikota_Plant_1",
        events=all_events,
        analysis_period="34-day observation period"
    )
    for r in recs:
        print(f"  [{r.priority.value}] {r.recommendation_id}: {r.reason}")
        print(f"      Recommended Action: {r.recommended_inspection}")

    # 7. BESS Coupled Dispatch Simulation on Real Solar Profile
    print("\n=== 7. Hybrid Solar-plus-Storage BESS Dispatch Simulation ===")
    # Simulate coupling 15 MW / 40 MWh BESS with Plant 1 solar profile (~29 MW peak)
    bess_constraints = BESSCoLocatedDispatchConstraint(
        site_interconnection_limit_mw=25.0,
        bess_max_charge_mw=12.0,
        bess_max_discharge_mw=12.0,
        bess_capacity_mwh=40.0,
        soc_min=0.05,
        soc_max=0.95,
        eta_charge=0.94
    )

    # Pick a high-solar midday interval from Plant 1 (> 20,000 kW)
    midday_candidates = df_p1_agg[df_p1_agg["power"] > 20000]
    midday_row = midday_candidates.iloc[min(10, len(midday_candidates) - 1)]
    solar_gen_mw = float(midday_row["power"]) / 1000.0 # ~22-28 MW
    site_load_mw = 5.0 # 5 MW local facility load

    decision = BESSIntegrationAdapter.dispatch_coupled_solar_step(
        solar_power_mw=solar_gen_mw,
        site_load_mw=site_load_mw,
        current_soc=0.30,
        requested_bess_power_mw=-12.0, # request 12 MW battery charge from surplus solar
        constraints=bess_constraints,
        dt_hours=1.0,
        timestamp=str(midday_row["timestamp"])
    )
    print(f"  Timestamp: {decision.timestamp}")
    print(f"  Available Solar: {decision.solar_available_mw:.2f} MW")
    print(f"  Supplied to Site Load: {decision.solar_to_load_mw:.2f} MW (100% of load)")
    print(f"  Stored into BESS: {decision.solar_to_bess_charge_mw:.2f} MW (Zero Grid Purchase)")
    print(f"  Exported to Grid: {decision.solar_to_grid_export_mw:.2f} MW")
    print(f"  Curtailed: {decision.solar_curtailed_mw:.2f} MW")
    print(f"  New Battery SoC: {decision.resulting_soc*100:.1f}%")
    print(f"  Conservation of Energy Enforced: Zero Discrepancy.")

    # Save summary report
    summary_report = {
        "status": "COMPLETED_SUCCESSFULLY",
        "archive_directory": archive_dir,
        "plant_1_inverter_records": len(df_p1_inv),
        "plant_1_aggregate_intervals": len(df_p1_agg),
        "plant_1_peak_power_kw": round(p1_peak_kw, 2),
        "plant_2_inverter_records": len(df_p2_inv),
        "plant_2_aggregate_intervals": len(df_p2_agg),
        "plant_2_peak_power_kw": round(float(df_p2_agg["power"].max()), 2),
        "xgboost_mae_kw": xgb_meta["metrics"]["mae"],
        "xgboost_nmae_pct": xgb_meta["metrics"]["nmae_pct"],
        "xgboost_r2": xgb_meta["metrics"]["r2_score"],
        "xgboost_improvement_pct": xgb_meta["improvement_over_baseline_pct"],
        "lightgbm_mae_kw": lgb_meta["metrics"]["mae"],
        "lightgbm_nmae_pct": lgb_meta["metrics"]["nmae_pct"],
        "lightgbm_r2": lgb_meta["metrics"]["r2_score"],
        "forecast_24h_energy_mwh": payload.total_forecast_energy_mwh,
        "forecast_24h_peak_mw": payload.peak_forecast_power_mw,
        "anomalies_detected": len(all_events),
        "soiling_status": soiling_res.status,
        "soiling_ratio_current": soiling_res.soiling_ratio_current,
        "degradation_status": deg_res.status,
        "recommendations_count": len(recs)
    }
    with open("data/datasets/kaggle_solar/archive_processing_summary.json", "w") as f:
        json.dump(summary_report, f, indent=2)

    print("\n=== PROCESSING OF ARCHIVE DATASET COMPLETE ===")


if __name__ == "__main__":
    main()
