import React from "react";
import {
  TrendingUp,
  Battery,
  Zap,
  DollarSign,
  ShieldCheck,
  RefreshCw,
  Play,
  AlertTriangle,
} from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ReferenceLine,
} from "recharts";
import {
  MarketSummary,
  BatteryState,
  BatteryConfig,
  DispatchPlanResponse,
} from "../types";

interface OverviewTabProps {
  summary: MarketSummary | null;
  telemetry: BatteryState | null;
  config: BatteryConfig | null;
  dispatchPlan: DispatchPlanResponse | null;
  onRefresh: () => void;
  onTriggerBacktest: () => void;
  onResetTwin: () => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  summary,
  telemetry,
  config,
  dispatchPlan,
  onRefresh,
  onTriggerBacktest,
  onResetTwin,
}) => {
  const socPct = telemetry ? (telemetry.soc * 100).toFixed(1) : "50.0";
  const sohPct = telemetry ? telemetry.state_of_health_pct.toFixed(1) : "100.0";
  const efc = telemetry ? telemetry.equivalent_full_cycles.toFixed(1) : "0.0";
  const currentPrice = summary ? summary.avg_price.toFixed(2) : "52.40";

  // Chart data from 24h dispatch plan
  const chartData =
    dispatchPlan?.schedule.map((item) => ({
      hour: `H${item.hour_index}`,
      time: item.timestamp.substring(11, 16),
      rtPrice: item.market_price,
      daPrice: item.day_ahead_price,
      powerMw: item.recommended_power_mw,
      soc: item.projected_soc_pct,
    })) ?? [];

  return (
    <div className="space-y-6">
      {/* Top Banner: Market Status */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <ShieldCheck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-bold text-slate-100">
                Market Provenance: CAISO SP-15 (California ISO)
              </span>
              <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-emerald-950 border border-emerald-800 text-emerald-400">
                VERIFIED BENCHMARK
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Duck-curve solar profile, 1-hour settlement interval, currency: USD ($/MWh), timezone: UTC-8.
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <button
            onClick={onRefresh}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 flex items-center space-x-1.5 transition"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Refresh Telemetry</span>
          </button>
          <button
            onClick={onTriggerBacktest}
            className="px-3.5 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-slate-900 text-xs font-bold rounded-lg transition flex items-center space-x-1.5"
          >
            <Play className="w-3.5 h-3.5" />
            <span>Run Strategy Backtest</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Market Price */}
        <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1.5">
            <span>Market Price (Avg)</span>
            <TrendingUp className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100 font-mono">
            ${currentPrice}
            <span className="text-xs font-normal text-slate-400 ml-1">/MWh</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1 flex justify-between">
            <span>Min: ${summary?.min_price.toFixed(1) ?? "0.0"}</span>
            <span>Max: ${summary?.max_price.toFixed(1) ?? "0.0"}</span>
          </div>
        </div>

        {/* Battery SoC */}
        <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1.5">
            <span>State of Charge (SoC)</span>
            <Battery className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 font-mono">
            {socPct}%
          </div>
          <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
            <div
              className="bg-emerald-400 h-full rounded-full transition-all duration-500"
              style={{ width: `${Math.min(100, Math.max(0, Number(socPct)))}%` }}
            />
          </div>
          <div className="text-[11px] text-slate-400 mt-1 flex justify-between">
            <span>Min: {((config?.soc_min ?? 0.05) * 100).toFixed(0)}%</span>
            <span>Max: {((config?.soc_max ?? 0.95) * 100).toFixed(0)}%</span>
          </div>
        </div>

        {/* Inverter Capacity */}
        <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1.5">
            <span>Power & Capacity</span>
            <Zap className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100 font-mono">
            {config?.power_mw ?? 50}
            <span className="text-xs font-normal text-slate-400 ml-1">MW</span>
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Capacity: <span className="text-slate-200 font-medium">{config?.capacity_mwh ?? 100} MWh</span> (2h C-rate)
          </p>
        </div>

        {/* Battery Health (SOH) */}
        <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1.5">
            <span>State of Health (SOH)</span>
            <ShieldCheck className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100 font-mono">
            {sohPct}%
          </div>
          <p className="text-xs text-slate-400 mt-1">
            Throughput: <span className="text-slate-200 font-medium">{efc} EFC</span> cycles
          </p>
        </div>

        {/* 24h Projected Net Margin */}
        <div className="bg-slate-900/90 border border-slate-800 p-4 rounded-xl">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-1.5">
            <span>24h Projected Net PnL</span>
            <DollarSign className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 font-mono">
            ${dispatchPlan?.total_predicted_net_pnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? "0.00"}
          </div>
          <p className="text-[11px] text-slate-400 mt-1">
            Net of losses, degradation & grid fees
          </p>
        </div>
      </div>

      {/* Main Chart: Electricity Prices vs 24h Dispatch Schedule */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-slate-800/80 gap-2">
          <div>
            <h2 className="text-base font-bold text-slate-100">
              24-Hour Electricity Market Pricing & Recommended Dispatch
            </h2>
            <p className="text-xs text-slate-400">
              Comparing Real-Time LMP ($/MWh), Day-Ahead Forward ($/MWh), and Battery Dispatch (MW: +Discharge, -Charge)
            </p>
          </div>
          <div className="flex items-center space-x-3 text-xs">
            <span className="flex items-center space-x-1.5">
              <span className="w-3 h-0.5 bg-cyan-400" />
              <span className="text-slate-300">Real-Time LMP</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <span className="w-3 h-0.5 bg-amber-400" />
              <span className="text-slate-300">Day-Ahead</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <span className="w-3 h-0.5 bg-emerald-400" />
              <span className="text-slate-300">Dispatch (MW)</span>
            </span>
          </div>
        </div>

        <div className="h-80 w-full mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 11 }} />
              <YAxis
                yAxisId="price"
                stroke="#64748b"
                tick={{ fontSize: 11 }}
                domain={['auto', 'auto']}
                unit="$"
              />
              <YAxis
                yAxisId="power"
                orientation="right"
                stroke="#64748b"
                tick={{ fontSize: 11 }}
                domain={[-60, 60]}
                unit="MW"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  fontSize: "12px",
                  borderRadius: "8px",
                }}
              />
              <ReferenceLine yAxisId="power" y={0} stroke="#475569" strokeDasharray="2 2" />
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="rtPrice"
                name="Real-Time Price ($/MWh)"
                stroke="#22d3ee"
                strokeWidth={2}
                dot={false}
              />
              <Line
                yAxisId="price"
                type="monotone"
                dataKey="daPrice"
                name="Day-Ahead Price ($/MWh)"
                stroke="#fbbf24"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                dot={false}
              />
              <Line
                yAxisId="power"
                type="stepAfter"
                dataKey="powerMw"
                name="Dispatch Power (MW)"
                stroke="#34d399"
                strokeWidth={2}
                dot={{ r: 3, fill: "#34d399" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bottom Grid: 24h Recommendation Details & Digital Twin Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Next Hours Dispatch Plan Highlights */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-bold text-slate-100 mb-3 flex items-center justify-between">
            <span>Upcoming Dispatch Highlights</span>
            <span className="text-xs font-normal text-slate-400">Next 6 Intervals</span>
          </h3>
          <div className="space-y-2.5">
            {dispatchPlan?.schedule.slice(0, 6).map((item) => {
              const isCharge = item.action_type === "CHARGE";
              const isDischarge = item.action_type === "DISCHARGE";
              return (
                <div
                  key={item.hour_index}
                  className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 flex items-center justify-between text-xs"
                >
                  <div className="flex items-center space-x-3">
                    <span className="font-mono text-slate-400 w-12">
                      {item.timestamp.substring(11, 16)}
                    </span>
                    <span
                      className={`px-2 py-0.5 rounded font-bold uppercase text-[10px] ${
                        isCharge
                          ? "bg-emerald-950 border border-emerald-800 text-emerald-400"
                          : isDischarge
                          ? "bg-cyan-950 border border-cyan-800 text-cyan-400"
                          : "bg-slate-800 border border-slate-700 text-slate-400"
                      }`}
                    >
                      {item.action_type}
                    </span>
                    <span className="font-mono font-bold text-slate-200">
                      {item.recommended_power_mw.toFixed(1)} MW
                    </span>
                  </div>

                  <div className="text-right">
                    <div className="font-mono text-slate-300">
                      ${item.market_price.toFixed(2)}/MWh
                    </div>
                    <div className="text-[11px] text-slate-400">
                      Net: <span className={item.net_margin >= 0 ? "text-emerald-400" : "text-rose-400"}>
                        ${item.net_margin.toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Operational Controls & Reset */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <h3 className="text-sm font-bold text-slate-100 mb-2">
              Digital Twin Asset Parameters
            </h3>
            <p className="text-xs text-slate-400 mb-4">
              Real-time state and constraint envelope for {config?.name ?? "Utility-Scale BESS"}.
            </p>

            <div className="space-y-3 text-xs">
              <div className="flex justify-between py-1.5 border-b border-slate-800">
                <span className="text-slate-400">Asset Identifier:</span>
                <span className="font-mono text-slate-200">{config?.asset_id}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-800">
                <span className="text-slate-400">Round-Trip Efficiency:</span>
                <span className="font-mono text-slate-200">
                  {(((config?.eta_charge ?? 0.94) * (config?.eta_discharge ?? 0.94)) * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-800">
                <span className="text-slate-400">Degradation Cost Model:</span>
                <span className="font-mono text-slate-200">
                  Throughput ($12.00/MWh)
                </span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-slate-800">
                <span className="text-slate-400">Inverter Ramp Rate:</span>
                <span className="font-mono text-slate-200">
                  {config?.ramp_rate_mw_per_min ?? 25} MW/min
                </span>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800 mt-4">
            <button
              onClick={onResetTwin}
              className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white rounded-lg text-xs font-semibold border border-slate-700 transition"
            >
              Reset Digital Twin to 50% SoC
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
