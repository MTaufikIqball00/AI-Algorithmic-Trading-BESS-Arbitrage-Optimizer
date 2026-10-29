import React from "react";
import {
  Activity,
  BatteryCharging,
  Cpu,
  Database,
  Flame,
  ShieldAlert,
  Radio,
} from "lucide-react";
import { SystemHealth } from "../types";

interface HeaderProps {
  health: SystemHealth | null;
  activeTab: string;
  setActiveTab: (tab: string) => void;
  onToggleKillSwitch: (active: boolean) => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  activeTab,
  setActiveTab,
  onToggleKillSwitch,
}) => {
  const killSwitchActive = health?.risk_controls.emergency_kill_switch ?? false;
  const isMlConnected = health?.ml_service.status === "CONNECTED";

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "market", label: "Market & Forecast" },
    { id: "battery", label: "Battery Digital Twin" },
    { id: "strategy", label: "Strategy Lab (PPO)" },
    { id: "dispatch", label: "Dispatch Planner" },
    { id: "backtesting", label: "Backtesting & Risk" },
    { id: "orders", label: "Bidding & Orders" },
    { id: "datasources", label: "Data & Governance" },
  ];

  return (
    <header className="border-b border-slate-800 bg-slate-900/95 sticky top-0 z-50 backdrop-blur">
      {/* Top Banner */}
      <div className="max-w-7xl mx-auto px-4 py-2.5 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="p-2 bg-cyan-500/10 border border-cyan-500/30 rounded-lg text-cyan-400">
            <BatteryCharging className="w-6 h-6" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-lg font-bold text-slate-100 tracking-tight">
                AI Algorithmic Trading & BESS Optimizer
              </h1>
              <span className="text-[10px] font-semibold tracking-wider uppercase px-2 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-300">
                CAISO SP-15
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Autonomous Battery Energy Storage Arbitrage & Price Forecasting Terminal
            </p>
          </div>
        </div>

        {/* System Status Indicators */}
        <div className="flex items-center space-x-4">
          <div className="hidden md:flex items-center space-x-3 text-xs">
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-slate-800/80 border border-slate-700/60">
              <Cpu className="w-3.5 h-3.5 text-cyan-400" />
              <span className="text-slate-300">Rust Core:</span>
              <span className="text-emerald-400 font-medium">8230 Active</span>
            </div>

            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-slate-800/80 border border-slate-700/60">
              <Activity className="w-3.5 h-3.5 text-indigo-400" />
              <span className="text-slate-300">ML Engine:</span>
              <span
                className={`font-medium ${
                  isMlConnected ? "text-emerald-400" : "text-amber-400"
                }`}
              >
                {health?.ml_service.status ?? "Probing"}
              </span>
            </div>

            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded bg-slate-800/80 border border-slate-700/60">
              <Database className="w-3.5 h-3.5 text-amber-400" />
              <span className="text-slate-300">Records:</span>
              <span className="text-slate-200 font-mono">
                {health?.market_dataset.loaded_records ?? 0} hrs
              </span>
            </div>
          </div>

          {/* Kill Switch Toggle */}
          <button
            onClick={() => onToggleKillSwitch(!killSwitchActive)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center space-x-1.5 border shadow-sm ${
              killSwitchActive
                ? "bg-rose-600 hover:bg-rose-500 text-white border-rose-400 animate-pulse"
                : "bg-slate-800 hover:bg-rose-950/60 text-slate-300 hover:text-rose-300 border-slate-700"
            }`}
          >
            <ShieldAlert className="w-4 h-4" />
            <span>{killSwitchActive ? "KILL SWITCH: ACTIVE" : "ARM KILL SWITCH"}</span>
          </button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="max-w-7xl mx-auto px-4 flex space-x-1 overflow-x-auto no-scrollbar border-t border-slate-800/60 text-sm">
        {tabs.map((t) => {
          const isActive = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`py-2.5 px-3.5 font-medium whitespace-nowrap transition-colors border-b-2 flex items-center space-x-1.5 ${
                isActive
                  ? "border-cyan-400 text-cyan-300 bg-cyan-950/20"
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700"
              }`}
            >
              <span>{t.label}</span>
            </button>
          );
        })}
      </div>
    </header>
  );
};
