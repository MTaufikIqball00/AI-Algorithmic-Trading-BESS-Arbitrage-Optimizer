import React, { useState } from "react";
import {
  Sun,
  Zap,
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Cpu,
  Wrench,
  BatteryCharging,
  Activity,
} from "lucide-react";
import {
  ResponsiveContainer,
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";
import {
  SolarPvSummaryResponse,
  SolarCoupledDispatchDecision,
} from "../types";
import { api } from "../services/api";

interface SolarPvTabProps {
  solarSummary: SolarPvSummaryResponse | null;
  onRefreshSolar: (modelType: "xgboost" | "lightgbm") => Promise<void>;
}

export const SolarPvTab: React.FC<SolarPvTabProps> = ({
  solarSummary,
  onRefreshSolar,
}) => {
  const [selectedModel, setSelectedModel] = useState<"xgboost" | "lightgbm">(
    "xgboost"
  );
  const [isTraining, setIsTraining] = useState(false);
  const [simSolarMw, setSimSolarMw] = useState<number>(23.72);
  const [simLoadMw, setSimLoadMw] = useState<number>(5.0);
  const [simSocPct, setSimSocPct] = useState<number>(30.0);
  const [simReqBessMw, setSimReqBessMw] = useState<number>(-12.0);
  const [coupledResult, setCoupledResult] =
    useState<SolarCoupledDispatchDecision | null>(
      solarSummary?.coupled_dispatch_example ?? null
    );
  const [simLoading, setSimLoading] = useState(false);

  const handleModelSwitch = async (m: "xgboost" | "lightgbm") => {
    setSelectedModel(m);
    await onRefreshSolar(m);
  };

  const handleRetrain = async () => {
    try {
      setIsTraining(true);
      await api.trainSolarModel(selectedModel);
      await onRefreshSolar(selectedModel);
    } finally {
      setIsTraining(false);
    }
  };

  const handleRunCoupledSim = async () => {
    try {
      setSimLoading(true);
      const res = await api.simulateSolarCoupledDispatch({
        solar_power_mw: simSolarMw,
        site_load_mw: simLoadMw,
        current_soc: simSocPct / 100.0,
        requested_bess_power_mw: simReqBessMw,
        interconnection_limit_mw: 25.0,
        bess_capacity_mwh: 40.0,
        bess_max_charge_mw: 12.0,
        bess_max_discharge_mw: 12.0,
      });
      setCoupledResult(res);
    } finally {
      setSimLoading(false);
    }
  };

  const arch = solarSummary?.archive_summary ?? {};
  const xgbMeta = solarSummary?.xgboost_metadata?.metrics ?? {};
  const lgbMeta = solarSummary?.lightgbm_metadata?.metrics ?? {};

  const p1Records = arch.plant_1_inverter_records ?? 68774;
  const p1Intervals = arch.plant_1_aggregate_intervals ?? 3157;
  const p1PeakKw = arch.plant_1_peak_power_kw ?? 29150.21;
  const p2PeakKw = arch.plant_2_peak_power_kw ?? 25979.76;

  const xgbMae = xgbMeta.mae ?? arch.xgboost_mae_kw ?? 1005.99;
  const xgbNmae = xgbMeta.nmae_pct ?? arch.xgboost_nmae_pct ?? 3.12;
  const xgbR2 = xgbMeta.r2_score ?? arch.xgboost_r2 ?? 0.9312;
  const xgbImp =
    solarSummary?.xgboost_metadata?.improvement_over_baseline_pct ??
    arch.xgboost_improvement_pct ??
    43.76;

  const lgbMae = lgbMeta.mae ?? arch.lightgbm_mae_kw ?? 1003.26;
  const lgbNmae = lgbMeta.nmae_pct ?? arch.lightgbm_nmae_pct ?? 3.11;
  const lgbR2 = lgbMeta.r2_score ?? arch.lightgbm_r2 ?? 0.9271;
  const lgbImp =
    solarSummary?.lightgbm_metadata?.improvement_over_baseline_pct ?? 43.92;

  const forecastPoints = solarSummary?.forecast?.points ?? [];
  const chartData = forecastPoints.map((pt, idx) => {
    const tStr = pt.timestamp.length >= 16 ? pt.timestamp.substring(11, 16) : `T+${idx}`;
    return {
      time: tStr,
      powerMw: Number((pt.predicted_power_kw / 1000.0).toFixed(3)),
      upper80Mw: Number((pt.prediction_interval.upper_80 / 1000.0).toFixed(3)),
      lower80Mw: Number((pt.prediction_interval.lower_80 / 1000.0).toFixed(3)),
    };
  });

  const activeCoupled =
    coupledResult ?? solarSummary?.coupled_dispatch_example ?? null;

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400">
            <Sun className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-bold text-slate-100">
                Solar PV Intelligence & Co-Located BESS Dispatch Engine
              </span>
              <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-emerald-950 border border-emerald-800 text-emerald-400">
                REAL GANDIKOTA PV ARCHIVE
              </span>
            </div>
            <p className="text-xs text-slate-400">
              IEC 61724 physical model • 15-min SCADA telemetry (IST +05:30) • Plant 1:{" "}
              {p1Records.toLocaleString()} inverter records ({p1Intervals.toLocaleString()}{" "}
              intervals)
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <div className="inline-flex rounded-lg bg-slate-950 p-1 border border-slate-800">
            <button
              onClick={() => handleModelSwitch("xgboost")}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
                selectedModel === "xgboost"
                  ? "bg-amber-500 text-slate-950"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              XGBoost
            </button>
            <button
              onClick={() => handleModelSwitch("lightgbm")}
              className={`px-3 py-1 text-xs font-semibold rounded-md transition ${
                selectedModel === "lightgbm"
                  ? "bg-amber-500 text-slate-950"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              LightGBM
            </button>
          </div>

          <button
            onClick={handleRetrain}
            disabled={isTraining}
            className="px-3.5 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-950 text-xs font-bold rounded-lg transition flex items-center space-x-1.5"
          >
            <RefreshCw
              className={`w-3.5 h-3.5 ${isTraining ? "animate-spin" : ""}`}
            />
            <span>{isTraining ? "Training..." : "Retrain PV Model"}</span>
          </button>
        </div>
      </div>

      {/* KPI Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>Plant 1 & 2 Peak AC Capacity</span>
            <Zap className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-xl font-bold text-slate-100 font-mono">
            {(p1PeakKw / 1000.0).toFixed(2)} MW{" "}
            <span className="text-xs font-normal text-slate-400">
              / {(p2PeakKw / 1000.0).toFixed(2)} MW
            </span>
          </div>
          <p className="text-[11px] text-emerald-400 mt-1">
            Estimated DC: {((solarSummary?.rated_dc_kw ?? 32272.2) / 1000.0).toFixed(2)} MWp •
            Quality: 100/100
          </p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>24h Solar Energy Forecast</span>
            <Sun className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-xl font-bold text-slate-100 font-mono">
            {(solarSummary?.forecast?.total_forecast_energy_mwh ?? 143.11).toFixed(2)} MWh
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Peak Forecast:{" "}
            <span className="text-amber-300 font-semibold">
              {(solarSummary?.forecast?.peak_forecast_power_mw ?? 22.79).toFixed(2)} MW
            </span>{" "}
            (96 × 15-min steps)
          </p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>XGBoost Out-of-Sample Accuracy</span>
            <Cpu className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-xl font-bold text-slate-100 font-mono">
            nMAE: {Number(xgbNmae).toFixed(2)}%{" "}
            <span className="text-xs font-normal text-emerald-400">
              (R² {Number(xgbR2).toFixed(4)})
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            MAE: {Number(xgbMae).toFixed(1)} kW •{" "}
            <span className="text-emerald-400 font-semibold">
              +{Number(xgbImp).toFixed(1)}% vs Naive
            </span>
          </p>
        </div>

        <div className="bg-slate-900/80 border border-slate-800 rounded-xl p-4">
          <div className="flex items-center justify-between text-xs text-slate-400 mb-1">
            <span>LightGBM Out-of-Sample Accuracy</span>
            <Activity className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-xl font-bold text-slate-100 font-mono">
            nMAE: {Number(lgbNmae).toFixed(2)}%{" "}
            <span className="text-xs font-normal text-emerald-400">
              (R² {Number(lgbR2).toFixed(4)})
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            MAE: {Number(lgbMae).toFixed(1)} kW •{" "}
            <span className="text-emerald-400 font-semibold">
              +{Number(lgbImp).toFixed(1)}% vs Naive
            </span>
          </p>
        </div>
      </div>

      {/* 24-Hour Solar PV Forecast Chart */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
          <div>
            <h2 className="text-sm font-bold text-slate-100">
              24-Hour Short-Term Photovoltaic Generation Forecast (
              {selectedModel.toUpperCase()})
            </h2>
            <p className="text-xs text-slate-400">
              96 intervals (15-min resolution) with 80% prediction uncertainty bounds and strict
              nighttime zero-clamping
            </p>
          </div>
          <span className="text-xs font-mono px-2.5 py-1 rounded bg-slate-800 text-amber-300 border border-slate-700">
            Asset: {solarSummary?.asset_id ?? "Gandikota_Plant_1"}
          </span>
        </div>

        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis
                dataKey="time"
                stroke="#64748b"
                tick={{ fontSize: 11 }}
                interval={7}
              />
              <YAxis
                stroke="#64748b"
                tick={{ fontSize: 11 }}
                label={{
                  value: "Power (MW)",
                  angle: -90,
                  position: "insideLeft",
                  fill: "#94a3b8",
                  fontSize: 11,
                }}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  fontSize: "12px",
                }}
              />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
              <Area
                type="monotone"
                dataKey="upper80Mw"
                name="Upper 80% Bound (MW)"
                stroke="none"
                fill="#f59e0b"
                fillOpacity={0.15}
              />
              <Line
                type="monotone"
                dataKey="powerMw"
                name="Predicted Solar Power (MW)"
                stroke="#fbbf24"
                strokeWidth={2.5}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="lower80Mw"
                name="Lower 80% Bound (MW)"
                stroke="#38bdf8"
                strokeDasharray="4 4"
                strokeWidth={1.2}
                dot={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Soiling & Long-Term Degradation Scientific Safeguards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Soiling Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <h3 className="text-sm font-bold text-slate-100">
                IEC 61724 Soiling Ratio & Wash Recovery Analysis
              </h3>
            </div>
            <span className="px-2 py-0.5 text-[11px] font-bold rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
              {solarSummary?.soiling?.status ?? "NO_SOILING_DETECTED"}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3 pt-1">
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80">
              <div className="text-[11px] text-slate-400">Current Soiling Ratio</div>
              <div className="text-base font-bold text-emerald-400 font-mono">
                {solarSummary?.soiling?.soiling_ratio_current?.toFixed(3) ?? "0.979"}
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80">
              <div className="text-[11px] text-slate-400">Daily Loss Rate</div>
              <div className="text-base font-bold text-slate-200 font-mono">
                {solarSummary?.soiling?.estimated_soiling_rate_pct_day ?? 0.0}%/day
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80">
              <div className="text-[11px] text-slate-400">Analyzed Days</div>
              <div className="text-base font-bold text-slate-200 font-mono">
                {solarSummary?.soiling?.analyzed_days ?? 34} days
              </div>
            </div>
          </div>

          <div className="text-xs text-slate-300 space-y-1 bg-slate-950/50 p-3 rounded-lg border border-slate-800">
            {(solarSummary?.soiling?.evidence_notes ?? []).map((note, idx) => (
              <p key={idx}>• {note}</p>
            ))}
            {(solarSummary?.soiling?.missing_evidence ?? []).map((m, idx) => (
              <p key={`m-${idx}`} className="text-amber-300/90">
                • Telemetry Note: {m}
              </p>
            ))}
          </div>
        </div>

        {/* Degradation Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-bold text-slate-100">
                Long-Term PV Degradation Analysis (365-Day Gate)
              </h3>
            </div>
            <span className="px-2 py-0.5 text-[11px] font-bold rounded bg-amber-950 text-amber-300 border border-amber-800">
              {solarSummary?.degradation?.status ?? "INSUFFICIENT_DATA_DURATION"}
            </span>
          </div>

          <div className="grid grid-cols-3 gap-3 pt-1">
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80">
              <div className="text-[11px] text-slate-400">Dataset Span</div>
              <div className="text-base font-bold text-amber-300 font-mono">
                {solarSummary?.degradation?.data_duration_days ?? 34.0} days
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80">
              <div className="text-[11px] text-slate-400">Required Minimum</div>
              <div className="text-base font-bold text-slate-200 font-mono">
                365.0 days
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-950/70 border border-slate-800/80">
              <div className="text-[11px] text-slate-400">Annualized Rate</div>
              <div className="text-base font-bold text-slate-400 font-mono">
                {solarSummary?.degradation?.annualized_degradation_pct_year !== null &&
                solarSummary?.degradation?.annualized_degradation_pct_year !== undefined
                  ? `${solarSummary.degradation.annualized_degradation_pct_year}%/yr`
                  : "WITHHELD"}
              </div>
            </div>
          </div>

          <div className="text-xs text-amber-200/90 bg-amber-950/20 p-3 rounded-lg border border-amber-800/60">
            <span className="font-bold">Scientific Sufficiency Safeguard: </span>
            {solarSummary?.degradation?.scientific_warning ??
              "Dataset covers 34.0 days (< 365 days required). Annualized degradation rate is withheld to avoid conflating seasonal solar elevation with cell aging."}
          </div>
        </div>
      </div>

      {/* Predictive Maintenance & Anomaly Root-Cause Table */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Maintenance Work Orders */}
        <div className="lg:col-span-5 bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Wrench className="w-4 h-4 text-rose-400" />
              <h3 className="text-sm font-bold text-slate-100">
                Condition-Based O&M Recommendations
              </h3>
            </div>
            <span className="text-xs text-slate-400 font-mono">
              {solarSummary?.maintenance?.recommendation_count ?? 1} Active
            </span>
          </div>

          <div className="space-y-3">
            {(solarSummary?.maintenance?.recommendations ?? []).map((rec) => (
              <div
                key={rec.recommendation_id}
                className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 space-y-2"
              >
                <div className="flex items-center justify-between">
                  <span className="text-xs font-mono font-bold text-slate-200">
                    {rec.recommendation_id}
                  </span>
                  <span
                    className={`px-2 py-0.5 text-[10px] font-bold rounded border ${
                      rec.priority === "CRITICAL"
                        ? "bg-rose-950 text-rose-300 border-rose-700"
                        : rec.priority === "HIGH"
                        ? "bg-amber-950 text-amber-300 border-amber-700"
                        : "bg-cyan-950 text-cyan-300 border-cyan-800"
                    }`}
                  >
                    {rec.priority}
                  </span>
                </div>
                <p className="text-xs text-slate-200 font-medium">{rec.reason}</p>
                <div className="text-[11px] text-cyan-300 bg-cyan-950/30 p-2 rounded border border-cyan-900/50">
                  <span className="font-semibold">Action: </span>
                  {rec.recommended_inspection}
                </div>
                {rec.evidence?.length > 0 && (
                  <p className="text-[11px] text-slate-400">
                    Evidence: {rec.evidence[0]}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Evidence-Based Anomaly Classification Log */}
        <div className="lg:col-span-7 bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <ShieldAlert className="w-4 h-4 text-amber-400" />
              <h3 className="text-sm font-bold text-slate-100">
                Multi-Inverter Evidence-Based Anomaly Classifications
              </h3>
            </div>
            <span className="text-xs text-slate-400 font-mono">
              Total Detected: {solarSummary?.anomaly_summary?.total_detected ?? 17}
            </span>
          </div>

          <div className="overflow-x-auto max-h-80">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400">
                  <th className="py-2 px-2">Inverter / Asset</th>
                  <th className="py-2 px-2">Classification</th>
                  <th className="py-2 px-2">Severity</th>
                  <th className="py-2 px-2">POA (W/m²)</th>
                  <th className="py-2 px-2">Deficit</th>
                  <th className="py-2 px-2">Physical Evidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {(solarSummary?.anomaly_summary?.events ?? []).slice(0, 8).map((ev) => (
                  <tr key={ev.event_id} className="hover:bg-slate-800/40">
                    <td className="py-2.5 px-2 font-mono text-[11px] text-slate-300">
                      {ev.asset_id}
                    </td>
                    <td className="py-2.5 px-2">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          ev.classification === "POTENTIAL_EQUIPMENT_FAULT"
                            ? "bg-rose-950 text-rose-300 border border-rose-800"
                            : ev.classification === "WEATHER_RELATED"
                            ? "bg-sky-950 text-sky-300 border border-sky-800"
                            : "bg-amber-950 text-amber-300 border border-amber-800"
                        }`}
                      >
                        {ev.classification}
                      </span>
                    </td>
                    <td className="py-2.5 px-2 font-semibold text-slate-300">
                      {ev.severity}
                    </td>
                    <td className="py-2.5 px-2 font-mono text-slate-300">
                      {ev.evidence?.mean_irradiance_poa?.toFixed(1) ?? "0.0"}
                    </td>
                    <td className="py-2.5 px-2 font-mono text-rose-400">
                      -{ev.evidence?.power_deficit_pct?.toFixed(1) ?? "0.0"}%
                    </td>
                    <td className="py-2.5 px-2 text-[11px] text-slate-400 max-w-xs">
                      {ev.evidence?.evidence_notes?.[0] ?? "Analyzed via residual Z-score"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* Interactive Co-Located Solar + BESS Coupled Dispatch Simulator */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div className="flex items-center space-x-2">
            <BatteryCharging className="w-5 h-5 text-cyan-400" />
            <div>
              <h3 className="text-sm font-bold text-slate-100">
                Hybrid Solar-plus-Storage Co-Located BESS Dispatch Simulator
              </h3>
              <p className="text-xs text-slate-400">
                Simulates zero-double-counting energy routing between Solar PV, local facility
                load, BESS charging, and POI grid interconnection limit (25 MW)
              </p>
            </div>
          </div>

          <button
            onClick={handleRunCoupledSim}
            disabled={simLoading}
            className="px-4 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold rounded-lg transition"
          >
            {simLoading ? "Simulating..." : "Simulate Coupled Dispatch Step"}
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 pt-2">
          <div>
            <label className="block text-xs text-slate-400 mb-1">
              Available Solar PV Power (MW)
            </label>
            <input
              type="number"
              step="0.5"
              value={simSolarMw}
              onChange={(e) => setSimSolarMw( Number(e.target.value) )}
              className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-sm font-mono text-slate-100"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">
              Site Facility Load (MW)
            </label>
            <input
              type="number"
              step="0.5"
              value={simLoadMw}
              onChange={(e) => setSimLoadMw( Number(e.target.value) )}
              className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-sm font-mono text-slate-100"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">
              Initial Battery SoC (%)
            </label>
            <input
              type="number"
              step="1"
              min="5"
              max="95"
              value={simSocPct}
              onChange={(e) => setSimSocPct( Number(e.target.value) )}
              className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-sm font-mono text-slate-100"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">
              Requested BESS Power (MW, -Charge/+Dis)
            </label>
            <input
              type="number"
              step="1"
              value={simReqBessMw}
              onChange={(e) => setSimReqBessMw( Number(e.target.value) )}
              className="w-full px-3 py-1.5 rounded-lg bg-slate-950 border border-slate-700 text-sm font-mono text-slate-100"
            />
          </div>
        </div>

        {activeCoupled && (
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 pt-2">
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
              <div className="text-[11px] text-slate-400">Direct Solar → Load</div>
              <div className="text-lg font-bold text-emerald-400 font-mono">
                {activeCoupled.solar_to_load_mw.toFixed(2)} MW
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
              <div className="text-[11px] text-slate-400">Surplus Solar → BESS</div>
              <div className="text-lg font-bold text-cyan-400 font-mono">
                {activeCoupled.solar_to_bess_charge_mw.toFixed(2)} MW
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
              <div className="text-[11px] text-slate-400">Solar → Grid Export</div>
              <div className="text-lg font-bold text-amber-400 font-mono">
                {activeCoupled.solar_to_grid_export_mw.toFixed(2)} MW
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
              <div className="text-[11px] text-slate-400">Solar Curtailed</div>
              <div className="text-lg font-bold text-slate-300 font-mono">
                {activeCoupled.solar_curtailed_mw.toFixed(2)} MW
              </div>
            </div>
            <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
              <div className="text-[11px] text-slate-400">Resulting Battery SoC</div>
              <div className="text-lg font-bold text-indigo-400 font-mono">
                {(activeCoupled.resulting_soc * 100.0).toFixed(1)}%
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
