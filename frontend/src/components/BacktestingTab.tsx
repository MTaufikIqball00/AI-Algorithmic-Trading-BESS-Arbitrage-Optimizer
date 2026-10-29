import React, { useState } from "react";
import {
  TrendingUp,
  Play,
  Download,
  Sliders,
  ShieldCheck,
  BarChart2,
  AlertCircle,
  CheckCircle,
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
  AreaChart,
  Area,
} from "recharts";
import { BacktestResponse, SensitivityResponse } from "../types";

interface BacktestingTabProps {
  backtestResult: BacktestResponse | null;
  sensitivity: SensitivityResponse | null;
  onRunBacktest: (strategy: "Idle" | "ThresholdHeuristic" | "ForecastHeuristic" | "PpoRl", startIdx: number, endIdx?: number) => Promise<void>;
  onFetchSensitivity: (param: string) => Promise<void>;
}

export const BacktestingTab: React.FC<BacktestingTabProps> = ({
  backtestResult,
  sensitivity,
  onRunBacktest,
  onFetchSensitivity,
}) => {
  const [selectedStrategy, setSelectedStrategy] = useState<"Idle" | "ThresholdHeuristic" | "ForecastHeuristic" | "PpoRl">("ThresholdHeuristic");
  const [windowDays, setWindowDays] = useState<number>(30);
  const [isRunning, setIsRunning] = useState(false);
  const [sensitivityParam, setSensitivityParam] = useState("round_trip_efficiency");

  const handleRun = async () => {
    setIsRunning(true);
    try {
      const hours = windowDays * 24;
      await onRunBacktest(selectedStrategy, 0, hours);
    } finally {
      setIsRunning(false);
    }
  };

  const handleParamChange = (param: string) => {
    setSensitivityParam(param);
    onFetchSensitivity(param);
  };

  const handleExportJson = () => {
    if (!backtestResult) return;
    const blob = new Blob([JSON.stringify(backtestResult, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `bess_backtest_${backtestResult.run_id.substring(0, 8)}.json`;
    a.click();
  };

  const metrics = backtestResult?.metrics;

  return (
    <div className="space-y-6">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center space-x-2">
            <span>Deterministic Backtesting & Risk Analytics</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Historical chronological replay without lookahead bias, accounting for round-trip losses, degradation, and fees.
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            onClick={handleExportJson}
            disabled={!backtestResult}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 text-slate-300 text-xs font-semibold rounded-lg border border-slate-700 flex items-center space-x-1.5 transition"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export Report (JSON)</span>
          </button>

          <button
            onClick={handleRun}
            disabled={isRunning}
            className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-900 text-xs font-bold rounded-lg transition flex items-center space-x-2 shadow-sm"
          >
            <Play className="w-3.5 h-3.5" />
            <span>{isRunning ? "Simulating..." : "Execute Backtest"}</span>
          </button>
        </div>
      </div>

      {/* Control Filter Bar */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-wrap items-center gap-4 text-xs">
        <div>
          <label className="block text-slate-400 mb-1 font-medium">Arbitrage Strategy</label>
          <select
            value={selectedStrategy}
            onChange={(e) => setSelectedStrategy(e.target.value as any)}
            className="p-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-medium focus:outline-none focus:border-cyan-500"
          >
            <option value="ThresholdHeuristic">Dynamic Price-Threshold (25th/75th Percentile)</option>
            <option value="ForecastHeuristic">XGBoost Day-Ahead Forecast Heuristic</option>
            <option value="PpoRl">PyTorch PPO Reinforcement Learning Policy</option>
            <option value="Idle">Baseline: Idle (No-Trade)</option>
          </select>
        </div>

        <div>
          <label className="block text-slate-400 mb-1 font-medium">Evaluation Window</label>
          <select
            value={windowDays}
            onChange={(e) => setWindowDays(parseInt(e.target.value))}
            className="p-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-medium focus:outline-none focus:border-cyan-500"
          >
            <option value={7}>1 Week (168 Hours)</option>
            <option value={30}>1 Month (720 Hours)</option>
            <option value={90}>1 Quarter (2,160 Hours)</option>
            <option value={365}>Full Year (8,784 Hours)</option>
          </select>
        </div>

        <div className="ml-auto text-right text-slate-400">
          <span className="text-[11px] block">Dataset: CAISO SP-15 2024</span>
          <span className="text-[11px] text-emerald-400 font-medium">Zero Future Leakage Replay</span>
        </div>
      </div>

      {/* KPI Performance Metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="text-[11px] text-slate-400">Net Profit</div>
          <div className="text-xl font-bold font-mono text-emerald-400 mt-0.5">
            ${metrics?.net_profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) ?? "0.00"}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Net of all losses & deg.</div>
        </div>

        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="text-[11px] text-slate-400">Annualized Sharpe</div>
          <div className="text-xl font-bold font-mono text-cyan-300 mt-0.5">
            {metrics?.sharpe_ratio.toFixed(2) ?? "0.00"}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Risk-adjusted return</div>
        </div>

        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="text-[11px] text-slate-400">Max Drawdown</div>
          <div className="text-xl font-bold font-mono text-rose-400 mt-0.5">
            ${metrics?.max_drawdown.toFixed(2) ?? "0.00"}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">
            {metrics?.max_drawdown_pct.toFixed(1) ?? "0.0"}% peak-to-trough
          </div>
        </div>

        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="text-[11px] text-slate-400">Win Rate</div>
          <div className="text-xl font-bold font-mono text-slate-100 mt-0.5">
            {metrics?.win_rate_pct.toFixed(1) ?? "0.0"}%
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Profitable dispatch hours</div>
        </div>

        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="text-[11px] text-slate-400">Cycles Run</div>
          <div className="text-xl font-bold font-mono text-amber-400 mt-0.5">
            {metrics?.equivalent_full_cycles.toFixed(1) ?? "0.0"} EFC
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Equivalent full cycles</div>
        </div>

        <div className="p-3.5 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="text-[11px] text-slate-400">Violations</div>
          <div className="text-xl font-bold font-mono text-emerald-400 mt-0.5">
            {metrics?.constraint_violations ?? 0}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Physical limits strictly kept</div>
        </div>
      </div>

      {/* Equity & Drawdown Chart */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h3 className="text-sm font-bold text-slate-100 mb-1">
          Cumulative Net PnL Equity Curve ($)
        </h3>
        <p className="text-xs text-slate-400 mb-4">
          Chronological equity trajectory accounting for real-time market clearing and battery degradation
        </p>

        <div className="h-72 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={backtestResult?.equity_curve ?? []}
              margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
            >
              <defs>
                <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                  <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="timestamp" stroke="#64748b" tick={{ fontSize: 10 }} tickFormatter={(ts) => ts.substring(5, 10)} />
              <YAxis stroke="#64748b" tick={{ fontSize: 11 }} unit="$" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  fontSize: "12px",
                }}
              />
              <Area
                type="monotone"
                dataKey="cumulative_pnl"
                stroke="#10b981"
                strokeWidth={2}
                fillOpacity={1}
                fill="url(#pnlGrad)"
                name="Cumulative Net PnL ($)"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Baseline Comparison Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h3 className="text-sm font-bold text-slate-100 mb-1">
          Fair Strategy & Baseline Accounting Comparison
        </h3>
        <p className="text-xs text-slate-400 mb-4">
          Evaluated on the exact same chronological interval slice with identical battery parameters and grid fee schedule.
        </p>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/40">
                <th className="py-2.5 px-3">Strategy</th>
                <th className="py-2.5 px-3 text-right">Throughput (MWh)</th>
                <th className="py-2.5 px-3 text-right">Cycles (EFC)</th>
                <th className="py-2.5 px-3 text-right">Degradation Cost</th>
                <th className="py-2.5 px-3 text-right">Transaction Fees</th>
                <th className="py-2.5 px-3 text-right">Net Operating Profit</th>
                <th className="py-2.5 px-3 text-right">Violations</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono">
              {backtestResult?.baseline_comparisons.map((b, idx) => (
                <tr key={idx} className="hover:bg-slate-800/30">
                  <td className="py-2.5 px-3 font-sans font-medium text-slate-300">
                    {b.strategy_name}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-200">
                    {b.total_throughput_mwh.toFixed(1)}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-200">
                    {b.equivalent_full_cycles.toFixed(1)}
                  </td>
                  <td className="py-2.5 px-3 text-right text-rose-400">
                    ${b.degradation_cost.toFixed(2)}
                  </td>
                  <td className="py-2.5 px-3 text-right text-slate-400">
                    ${b.transaction_fees.toFixed(2)}
                  </td>
                  <td className="py-2.5 px-3 text-right font-bold text-emerald-400">
                    ${b.net_profit.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </td>
                  <td className="py-2.5 px-3 text-right text-emerald-400">
                    {b.constraint_violations}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Sensitivity Analysis Section */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-3 border-b border-slate-800 gap-2">
          <div>
            <h3 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
              <Sliders className="w-4 h-4 text-cyan-400" />
              <span>Sensitivity Analysis</span>
            </h3>
            <p className="text-xs text-slate-400">
              Assessing how net arbitrage profit responds to parameter variations (±20% sweep)
            </p>
          </div>

          <div className="flex items-center space-x-2 text-xs">
            <span className="text-slate-400">Parameter:</span>
            <select
              value={sensitivityParam}
              onChange={(e) => handleParamChange(e.target.value)}
              className="p-1.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-cyan-500 font-medium"
            >
              <option value="round_trip_efficiency">Round-Trip Efficiency (η_rt)</option>
              <option value="cell_replacement_cost">Cell Replacement Cost ($/MWh)</option>
              <option value="power_mw">Inverter Power Rating (MW)</option>
            </select>
          </div>
        </div>

        <div className="h-64 w-full mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={sensitivity?.curve ?? []}
              margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="parameter_value" stroke="#64748b" tick={{ fontSize: 11 }} />
              <YAxis stroke="#64748b" tick={{ fontSize: 11 }} unit="$" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  fontSize: "12px",
                }}
              />
              <Line
                type="monotone"
                dataKey="net_profit"
                name="Net Profit ($)"
                stroke="#22d3ee"
                strokeWidth={2.5}
                dot={{ r: 4, fill: "#22d3ee" }}
              />
              <Line
                type="monotone"
                dataKey="degradation_cost"
                name="Degradation Cost ($)"
                stroke="#f43f5e"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                dot={{ r: 3, fill: "#f43f5e" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
