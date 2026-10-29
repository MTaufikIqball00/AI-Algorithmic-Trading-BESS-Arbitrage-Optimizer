import React, { useState } from "react";
import {
  Calendar,
  Zap,
  TrendingUp,
  DollarSign,
  Filter,
  CheckCircle,
  Clock,
} from "lucide-react";
import { DispatchPlanResponse } from "../types";

interface DispatchPlannerTabProps {
  dispatchPlan: DispatchPlanResponse | null;
}

export const DispatchPlannerTab: React.FC<DispatchPlannerTabProps> = ({
  dispatchPlan,
}) => {
  const [filterAction, setFilterAction] = useState<string>("ALL");

  if (!dispatchPlan) {
    return (
      <div className="p-8 text-center bg-slate-900 border border-slate-800 rounded-xl">
        <p className="text-slate-400 text-sm">Generating 24-hour lookahead dispatch schedule...</p>
      </div>
    );
  }

  const items = dispatchPlan.schedule.filter((it) => {
    if (filterAction === "ALL") return true;
    return it.action_type === filterAction;
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center space-x-2">
            <span>24-Hour Lookahead Dispatch Planner</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Optimized hourly schedule factoring in price arbitrage, round-trip efficiency losses, cell degradation, and grid connection limits.
          </p>
        </div>

        {/* Action Filters */}
        <div className="flex items-center space-x-1.5 p-1 bg-slate-900 border border-slate-800 rounded-lg text-xs">
          <button
            onClick={() => setFilterAction("ALL")}
            className={`px-3 py-1 rounded font-medium transition ${
              filterAction === "ALL"
                ? "bg-slate-800 text-cyan-300 font-bold"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            All (24)
          </button>
          <button
            onClick={() => setFilterAction("CHARGE")}
            className={`px-3 py-1 rounded font-medium transition ${
              filterAction === "CHARGE"
                ? "bg-emerald-950 text-emerald-400 font-bold border border-emerald-800"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Charging Only
          </button>
          <button
            onClick={() => setFilterAction("DISCHARGE")}
            className={`px-3 py-1 rounded font-medium transition ${
              filterAction === "DISCHARGE"
                ? "bg-cyan-950 text-cyan-400 font-bold border border-cyan-800"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            Discharging Only
          </button>
        </div>
      </div>

      {/* Summary KPI Banner */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="text-xs text-slate-400 mb-1">Total Predicted Net Profit</div>
          <div className="text-2xl font-bold font-mono text-emerald-400">
            ${dispatchPlan.total_predicted_net_pnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
          <div className="text-[11px] text-slate-400 mt-1">24-hour arbitrage run</div>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="text-xs text-slate-400 mb-1">Total Energy Charged</div>
          <div className="text-2xl font-bold font-mono text-slate-100">
            {dispatchPlan.total_charge_mwh.toFixed(1)}
            <span className="text-xs font-normal text-slate-400 ml-1">MWh</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Absorbed during valley/solar hours</div>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="text-xs text-slate-400 mb-1">Total Energy Discharged</div>
          <div className="text-2xl font-bold font-mono text-slate-100">
            {dispatchPlan.total_discharge_mwh.toFixed(1)}
            <span className="text-xs font-normal text-slate-400 ml-1">MWh</span>
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Dispatched during evening peak</div>
        </div>

        <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
          <div className="text-xs text-slate-400 mb-1">State of Charge Trajectory</div>
          <div className="text-2xl font-bold font-mono text-cyan-400">
            {dispatchPlan.initial_soc_pct}% → {dispatchPlan.final_projected_soc_pct}%
          </div>
          <div className="text-[11px] text-slate-400 mt-1">Maintained strictly within 5% - 95%</div>
        </div>
      </div>

      {/* Dispatch Schedule Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/60">
                <th className="py-3 px-3.5">Interval</th>
                <th className="py-3 px-3">Time</th>
                <th className="py-3 px-3 text-right">RT Price</th>
                <th className="py-3 px-3 text-right">DA Price</th>
                <th className="py-3 px-3 text-center">Action</th>
                <th className="py-3 px-3 text-right">Power</th>
                <th className="py-3 px-3 text-right">Proj. SoC</th>
                <th className="py-3 px-3 text-right">Revenue</th>
                <th className="py-3 px-3 text-right">Cost</th>
                <th className="py-3 px-3 text-right">Degradation</th>
                <th className="py-3 px-3 text-right">Net Margin</th>
                <th className="py-3 px-4">Explanatory Rationale</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
              {items.map((row) => {
                const isCharge = row.action_type === "CHARGE";
                const isDischarge = row.action_type === "DISCHARGE";

                return (
                  <tr key={row.hour_index} className="hover:bg-slate-800/30 transition-colors">
                    <td className="py-3 px-3.5 font-bold text-slate-400">H{row.hour_index}</td>
                    <td className="py-3 px-3 text-slate-200">{row.timestamp.substring(11, 16)}</td>
                    <td className="py-3 px-3 text-right font-bold text-cyan-300">
                      ${row.market_price.toFixed(2)}
                    </td>
                    <td className="py-3 px-3 text-right text-amber-300/90">
                      ${row.day_ahead_price.toFixed(2)}
                    </td>
                    <td className="py-3 px-3 text-center">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase ${
                          isCharge
                            ? "bg-emerald-950 border border-emerald-800 text-emerald-400"
                            : isDischarge
                            ? "bg-cyan-950 border border-cyan-800 text-cyan-400"
                            : "bg-slate-800 border border-slate-700 text-slate-400"
                        }`}
                      >
                        {row.action_type}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right font-bold text-slate-100">
                      {row.recommended_power_mw > 0 ? `+${row.recommended_power_mw.toFixed(1)}` : row.recommended_power_mw.toFixed(1)} MW
                    </td>
                    <td className="py-3 px-3 text-right text-emerald-400 font-bold">
                      {row.projected_soc_pct.toFixed(1)}%
                    </td>
                    <td className="py-3 px-3 text-right text-slate-200">
                      ${row.predicted_revenue.toFixed(2)}
                    </td>
                    <td className="py-3 px-3 text-right text-slate-400">
                      {row.predicted_cost > 0 ? `-$${row.predicted_cost.toFixed(2)}` : "$0.00"}
                    </td>
                    <td className="py-3 px-3 text-right text-rose-400">
                      {row.predicted_degradation_cost > 0 ? `-$${row.predicted_degradation_cost.toFixed(2)}` : "$0.00"}
                    </td>
                    <td
                      className={`py-3 px-3 text-right font-bold ${
                        row.net_margin > 0
                          ? "text-emerald-400"
                          : row.net_margin < 0
                          ? "text-rose-400"
                          : "text-slate-400"
                      }`}
                    >
                      {row.net_margin >= 0 ? `+$${row.net_margin.toFixed(2)}` : `-$${Math.abs(row.net_margin).toFixed(2)}`}
                    </td>
                    <td className="py-3 px-4 font-sans text-xs text-slate-400 max-w-xs truncate">
                      {row.rationale}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
