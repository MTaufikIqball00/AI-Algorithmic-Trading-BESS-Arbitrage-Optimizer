import React, { useState } from "react";
import {
  Battery,
  Zap,
  Sliders,
  ShieldCheck,
  RefreshCw,
  AlertCircle,
  Save,
  Activity,
} from "lucide-react";
import { BatteryConfig, BatteryState } from "../types";

interface BatteryTwinTabProps {
  config: BatteryConfig | null;
  telemetry: BatteryState | null;
  onUpdateConfig: (config: BatteryConfig) => Promise<void>;
  onResetTwin: () => Promise<void>;
}

export const BatteryTwinTab: React.FC<BatteryTwinTabProps> = ({
  config,
  telemetry,
  onUpdateConfig,
  onResetTwin,
}) => {
  const [formData, setFormData] = useState<BatteryConfig>(
    config ?? {
      asset_id: "BESS_CAISO_1",
      name: "CAISO Utility-Scale 100MWh/50MW LFP BESS",
      capacity_mwh: 100.0,
      power_mw: 50.0,
      soc_min: 0.05,
      soc_max: 0.95,
      eta_charge: 0.94,
      eta_discharge: 0.94,
      cell_replacement_cost_per_mwh: 120000.0,
      cycle_life_nominal: 5000.0,
      transaction_fee_per_mwh: 0.50,
      ramp_rate_mw_per_min: 25.0,
    }
  );

  const [saveStatus, setSaveStatus] = useState<string | null>(null);

  const handleChange = (field: keyof BatteryConfig, val: any) => {
    setFormData((prev) => ({
      ...prev,
      [field]: val,
    }));
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await onUpdateConfig(formData);
      setSaveStatus("Configuration successfully updated in backend!");
      setTimeout(() => setSaveStatus(null), 3000);
    } catch (e: any) {
      setSaveStatus(`Failed to update: ${e.message}`);
    }
  };

  const roundTripEff = (formData.eta_charge * formData.eta_discharge * 100).toFixed(1);
  const cRate = (formData.capacity_mwh / formData.power_mw).toFixed(1);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center space-x-2">
            <span>Battery Digital Twin & Degradation Model</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Physics-grounded electrochemical digital twin simulating cell capacity, round-trip efficiency losses, and cycle aging.
          </p>
        </div>

        <button
          onClick={onResetTwin}
          className="px-3.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 flex items-center space-x-1.5 transition"
        >
          <RefreshCw className="w-3.5 h-3.5 text-cyan-400" />
          <span>Reset Twin to 50% SoC</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Configuration Form */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-6">
          <form onSubmit={handleSave} className="space-y-5">
            <h3 className="text-sm font-bold text-slate-100 flex items-center space-x-2 pb-3 border-b border-slate-800">
              <Sliders className="w-4 h-4 text-cyan-400" />
              <span>Asset Hardware & Physics Parameters</span>
            </h3>

            {saveStatus && (
              <div className="p-3 bg-cyan-950/60 border border-cyan-800 rounded-lg text-xs font-medium text-cyan-300">
                {saveStatus}
              </div>
            )}

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Asset Name</label>
                <input
                  type="text"
                  value={formData.name}
                  onChange={(e) => handleChange("name", e.target.value)}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-cyan-500 font-medium"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Asset Identifier</label>
                <input
                  type="text"
                  value={formData.asset_id}
                  disabled
                  className="w-full p-2.5 bg-slate-950/50 border border-slate-800/80 rounded-lg text-slate-400 font-mono"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Nominal Energy Capacity (MWh)</label>
                <input
                  type="number"
                  step="1"
                  value={formData.capacity_mwh}
                  onChange={(e) => handleChange("capacity_mwh", parseFloat(e.target.value))}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Inverter Max Power (MW)</label>
                <input
                  type="number"
                  step="1"
                  value={formData.power_mw}
                  onChange={(e) => handleChange("power_mw", parseFloat(e.target.value))}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">SoC Min Limit (Operating Reserve)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="0.5"
                  value={formData.soc_min}
                  onChange={(e) => handleChange("soc_min", parseFloat(e.target.value))}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                />
                <span className="text-[10px] text-slate-400">Current: {(formData.soc_min * 100).toFixed(0)}%</span>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">SoC Max Limit (Cell Ceiling)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0.5"
                  max="1.0"
                  value={formData.soc_max}
                  onChange={(e) => handleChange("soc_max", parseFloat(e.target.value))}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                />
                <span className="text-[10px] text-slate-400">Current: {(formData.soc_max * 100).toFixed(0)}%</span>
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Charging Efficiency (η_charge)</label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.eta_charge}
                  onChange={(e) => handleChange("eta_charge", parseFloat(e.target.value))}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Discharging Efficiency (η_discharge)</label>
                <input
                  type="number"
                  step="0.01"
                  value={formData.eta_discharge}
                  onChange={(e) => handleChange("eta_discharge", parseFloat(e.target.value))}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Cell Replacement Cost ($/MWh)</label>
                <input
                  type="number"
                  step="1000"
                  value={formData.cell_replacement_cost_per_mwh}
                  onChange={(e) => handleChange("cell_replacement_cost_per_mwh", parseFloat(e.target.value))}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Nominal Cycle Life (Cycles at 80% DoD)</label>
                <input
                  type="number"
                  step="100"
                  value={formData.cycle_life_nominal}
                  onChange={(e) => handleChange("cycle_life_nominal", parseFloat(e.target.value))}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            <div className="pt-2 flex justify-end">
              <button
                type="submit"
                className="px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-slate-900 font-bold rounded-lg text-xs flex items-center space-x-1.5 shadow-sm transition"
              >
                <Save className="w-4 h-4" />
                <span>Save Asset Parameters</span>
              </button>
            </div>
          </form>
        </div>

        {/* Right: Real-time Telemetry & Degradation Summary */}
        <div className="space-y-6">
          {/* Live Telemetry Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
            <h3 className="text-sm font-bold text-slate-100 mb-3 flex items-center space-x-2">
              <Activity className="w-4 h-4 text-emerald-400" />
              <span>Real-Time Digital Twin Telemetry</span>
            </h3>

            <div className="space-y-4 text-xs">
              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-slate-400">Current SoC:</span>
                  <span className="font-mono font-bold text-emerald-400 text-sm">
                    {telemetry ? (telemetry.soc * 100).toFixed(1) : "50.0"}%
                  </span>
                </div>
                <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                  <div
                    className="bg-emerald-400 h-full rounded-full transition-all duration-300"
                    style={{ width: `${Math.min(100, Math.max(0, (telemetry?.soc ?? 0.5) * 100))}%` }}
                  />
                </div>
              </div>

              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 space-y-2">
                <div className="flex justify-between">
                  <span className="text-slate-400">State of Health (SOH):</span>
                  <span className="font-mono text-slate-200">
                    {telemetry?.state_of_health_pct.toFixed(2) ?? "100.00"}%
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Equivalent Full Cycles:</span>
                  <span className="font-mono text-slate-200">
                    {telemetry?.equivalent_full_cycles.toFixed(2) ?? "0.00"} EFC
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Cumulative Throughput:</span>
                  <span className="font-mono text-slate-200">
                    {telemetry?.total_throughput_mwh.toFixed(1) ?? "0.0"} MWh
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Degradation Cost Incurred:</span>
                  <span className="font-mono text-rose-400">
                    ${telemetry?.cumulative_degradation_cost.toFixed(2) ?? "0.00"}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Derived Physics Card */}
          <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 text-xs space-y-3">
            <h3 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
              <Zap className="w-4 h-4 text-cyan-400" />
              <span>Calculated Physical Metrics</span>
            </h3>

            <div className="flex justify-between py-1.5 border-b border-slate-800">
              <span className="text-slate-400">Round-Trip Efficiency:</span>
              <span className="font-mono font-bold text-cyan-300">{roundTripEff}%</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800">
              <span className="text-slate-400">Energy-to-Power Ratio:</span>
              <span className="font-mono text-slate-200">{cRate} Hours duration</span>
            </div>
            <div className="flex justify-between py-1.5 border-b border-slate-800">
              <span className="text-slate-400">Throughput Degradation Rate:</span>
              <span className="font-mono text-slate-200">
                ${(formData.cell_replacement_cost_per_mwh / (2 * formData.cycle_life_nominal)).toFixed(2)}/MWh
              </span>
            </div>
            <div className="flex justify-between py-1.5">
              <span className="text-slate-400">Usable Capacity Window:</span>
              <span className="font-mono text-emerald-400">
                {((formData.soc_max - formData.soc_min) * formData.capacity_mwh).toFixed(1)} MWh
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
