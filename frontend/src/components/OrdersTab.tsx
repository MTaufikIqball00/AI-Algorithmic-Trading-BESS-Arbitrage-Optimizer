import React, { useState } from "react";
import {
  FileText,
  Send,
  Lock,
  ShieldAlert,
  ShieldCheck,
  Clock,
  AlertTriangle,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { PaperOrder, BatteryConfig, BatteryState } from "../types";

interface OrdersTabProps {
  orders: PaperOrder[];
  config: BatteryConfig | null;
  telemetry: BatteryState | null;
  killSwitchActive: boolean;
  onSubmitOrder: (order: {
    asset_id: string;
    side: "Charge" | "Discharge" | "Idle";
    power_mw: number;
    limit_price?: number;
  }) => Promise<void>;
  onToggleKillSwitch: (active: boolean) => void;
}

export const OrdersTab: React.FC<OrdersTabProps> = ({
  orders,
  config,
  telemetry,
  killSwitchActive,
  onSubmitOrder,
  onToggleKillSwitch,
}) => {
  const [side, setSide] = useState<"Charge" | "Discharge">("Charge");
  const [powerMw, setPowerMw] = useState<number>(25.0);
  const [limitPrice, setLimitPrice] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [submitFeedback, setSubmitFeedback] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const currentSoc = telemetry ? telemetry.soc : 0.50;
  const maxPower = config?.power_mw ?? 50.0;

  // Pre-trade validation check
  const isPowerExceeded = powerMw > maxPower;
  const isSocBlocked =
    (side === "Charge" && currentSoc >= (config?.soc_max ?? 0.95) - 0.01) ||
    (side === "Discharge" && currentSoc <= (config?.soc_min ?? 0.05) + 0.01);

  const canSubmit = !killSwitchActive && !isPowerExceeded && !isSocBlocked && powerMw > 0;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;

    setSubmitting(true);
    setSubmitFeedback(null);
    try {
      await onSubmitOrder({
        asset_id: config?.asset_id ?? "BESS_CAISO_1",
        side,
        power_mw: powerMw,
        limit_price: limitPrice ? parseFloat(limitPrice) : undefined,
      });
      setSubmitFeedback({
        success: true,
        message: `Paper order for ${powerMw} MW (${side}) filled successfully!`,
      });
    } catch (err: any) {
      setSubmitFeedback({
        success: false,
        message: err.message,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center space-x-2">
            <span>Bidding Execution & Paper Order Desk</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Paper execution simulator with realistic slippage, pre-trade risk validation, and audit logging. Live mode strictly locked.
          </p>
        </div>

        <button
          onClick={() => onToggleKillSwitch(!killSwitchActive)}
          className={`px-3.5 py-2 rounded-lg text-xs font-bold transition flex items-center space-x-2 border shadow-sm ${
            killSwitchActive
              ? "bg-rose-600 hover:bg-rose-500 text-white border-rose-400 animate-pulse"
              : "bg-slate-800 hover:bg-rose-950/40 text-slate-300 hover:text-rose-300 border-slate-700"
          }`}
        >
          <ShieldAlert className="w-4 h-4" />
          <span>{killSwitchActive ? "EMERGENCY HALT ACTIVE" : "ARM KILL SWITCH"}</span>
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Paper Order Entry Form */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
                <Send className="w-4 h-4 text-cyan-400" />
                <span>Submit Paper Order</span>
              </h3>
              <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-cyan-300">
                PAPER SIMULATOR
              </span>
            </div>

            {submitFeedback && (
              <div
                className={`p-3 rounded-lg text-xs flex items-center space-x-2 border ${
                  submitFeedback.success
                    ? "bg-emerald-950/50 border-emerald-800 text-emerald-300"
                    : "bg-rose-950/50 border-rose-800 text-rose-300"
                }`}
              >
                {submitFeedback.success ? (
                  <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                ) : (
                  <XCircle className="w-4 h-4 shrink-0 text-rose-400" />
                )}
                <span>{submitFeedback.message}</span>
              </div>
            )}

            <div className="space-y-3 text-xs">
              <div>
                <label className="block text-slate-400 mb-1">Dispatch Action (Side)</label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setSide("Charge")}
                    className={`py-2 px-3 rounded-lg font-bold border transition ${
                      side === "Charge"
                        ? "bg-emerald-950 border-emerald-500 text-emerald-300"
                        : "bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Charge (Draw Power)
                  </button>
                  <button
                    type="button"
                    onClick={() => setSide("Discharge")}
                    className={`py-2 px-3 rounded-lg font-bold border transition ${
                      side === "Discharge"
                        ? "bg-cyan-950 border-cyan-500 text-cyan-300"
                        : "bg-slate-950 border-slate-800 text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    Discharge (Feed Grid)
                  </button>
                </div>
              </div>

              <div>
                <div className="flex justify-between items-center mb-1">
                  <label className="text-slate-400">Power Rating (MW)</label>
                  <span className="font-mono text-slate-400">Max: {maxPower} MW</span>
                </div>
                <input
                  type="number"
                  step="0.5"
                  min="0.5"
                  max={maxPower}
                  value={powerMw}
                  onChange={(e) => setPowerMw(parseFloat(e.target.value) || 0)}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-slate-400 mb-1">Limit Price ($/MWh, optional)</label>
                <input
                  type="number"
                  step="0.1"
                  placeholder="Market Order (Best Available)"
                  value={limitPrice}
                  onChange={(e) => setLimitPrice(e.target.value)}
                  className="w-full p-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-cyan-500 placeholder:text-slate-600"
                />
              </div>

              {/* Pre-trade Risk Manager Status */}
              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80 space-y-1.5 mt-2">
                <span className="text-slate-400 font-semibold block mb-1">Pre-Trade Risk Checks:</span>
                <div className="flex items-center space-x-2 text-[11px]">
                  {killSwitchActive ? (
                    <XCircle className="w-3.5 h-3.5 text-rose-400" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  )}
                  <span className={killSwitchActive ? "text-rose-400" : "text-slate-300"}>
                    Emergency Kill-Switch (Halt Check)
                  </span>
                </div>
                <div className="flex items-center space-x-2 text-[11px]">
                  {isPowerExceeded ? (
                    <XCircle className="w-3.5 h-3.5 text-rose-400" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  )}
                  <span className={isPowerExceeded ? "text-rose-400" : "text-slate-300"}>
                    Inverter Power Capacity Envelope (≤ {maxPower} MW)
                  </span>
                </div>
                <div className="flex items-center space-x-2 text-[11px]">
                  {isSocBlocked ? (
                    <XCircle className="w-3.5 h-3.5 text-rose-400" />
                  ) : (
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                  )}
                  <span className={isSocBlocked ? "text-rose-400" : "text-slate-300"}>
                    SoC Reserve Envelope (Current: {(currentSoc * 100).toFixed(1)}%)
                  </span>
                </div>
              </div>
            </div>

            <button
              type="submit"
              disabled={!canSubmit || submitting}
              className="w-full py-2.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 text-slate-900 font-bold rounded-lg text-xs transition flex items-center justify-center space-x-2 shadow-sm"
            >
              <Send className="w-3.5 h-3.5" />
              <span>{submitting ? "Routing Order..." : "Submit Paper Order"}</span>
            </button>
          </form>
        </div>

        {/* Right: Live Market Gateway Safety Gate */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
                <Lock className="w-4 h-4 text-amber-400" />
                <span>Live Market Gateway Integration</span>
              </h3>
              <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-rose-950 border border-rose-800 text-rose-400">
                HARD LOCKED • NOT CONFIGURED
              </span>
            </div>

            <div className="p-4 bg-amber-950/20 border border-amber-800/60 rounded-xl text-xs text-amber-300 mt-4 space-y-2">
              <div className="font-bold flex items-center space-x-1.5">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <span>Live Market Safeguard Specification</span>
              </div>
              <p className="text-slate-300 text-[11px]">
                Live transmission grid dispatch requires strict regulatory compliance. The live execution adapter is hardwired to reject orders until all prerequisite criteria below are met and certified.
              </p>
            </div>

            <div className="mt-4 space-y-2.5 text-xs">
              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="font-semibold text-slate-200 block">CAISO Scheduling Coordinator (SC)</span>
                  <span className="text-[11px] text-slate-400">Official ISO market participant accreditation</span>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                  MISSING
                </span>
              </div>

              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="font-semibold text-slate-200 block">EIM / Automated Dispatch System (ADS) API</span>
                  <span className="text-[11px] text-slate-400">Secured mutual TLS client certificates</span>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                  UNCONFIGURED
                </span>
              </div>

              <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="font-semibold text-slate-200 block">Dual-Party Cryptographic Sign-Off</span>
                  <span className="text-[11px] text-slate-400">Human operator authorization required before arming</span>
                </div>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                  LOCKED
                </span>
              </div>
            </div>
          </div>

          <div className="pt-4 border-t border-slate-800 text-[11px] text-slate-500">
            Live orders are currently routed through the zero-risk Paper Trading Simulator with realistic orderbook latency and slippage.
          </div>
        </div>
      </div>

      {/* Order History Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h3 className="text-sm font-bold text-slate-100 mb-3 flex items-center space-x-2">
          <FileText className="w-4 h-4 text-cyan-400" />
          <span>Paper Order Execution History</span>
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/60">
                <th className="py-2.5 px-3">Order ID</th>
                <th className="py-2.5 px-3">Timestamp</th>
                <th className="py-2.5 px-3">Side</th>
                <th className="py-2.5 px-3 text-right">Requested Power</th>
                <th className="py-2.5 px-3 text-right">Filled Power</th>
                <th className="py-2.5 px-3 text-right">Exec Price</th>
                <th className="py-2.5 px-3 text-right">Latency</th>
                <th className="py-2.5 px-3 text-center">Status</th>
                <th className="py-2.5 px-3">Notes</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
              {orders.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-6 text-center text-slate-500 font-sans">
                    No paper orders placed yet. Use the form above to execute a simulated dispatch order.
                  </td>
                </tr>
              ) : (
                orders.map((o) => (
                  <tr key={o.order_id} className="hover:bg-slate-800/30">
                    <td className="py-2.5 px-3 font-bold text-cyan-400">{o.order_id}</td>
                    <td className="py-2.5 px-3 text-slate-400">{o.timestamp.substring(11, 19)}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          o.side === "Charge"
                            ? "bg-emerald-950 text-emerald-400 border border-emerald-800"
                            : "bg-cyan-950 text-cyan-400 border border-cyan-800"
                        }`}
                      >
                        {o.side}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-right">{o.requested_power_mw.toFixed(1)} MW</td>
                    <td className="py-2.5 px-3 text-right font-bold text-slate-100">
                      {o.filled_power_mw.toFixed(1)} MW
                    </td>
                    <td className="py-2.5 px-3 text-right font-bold text-slate-200">
                      ${o.execution_price.toFixed(2)}/MWh
                    </td>
                    <td className="py-2.5 px-3 text-right text-slate-400">{o.latency_ms} ms</td>
                    <td className="py-2.5 px-3 text-center">
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 border border-emerald-800 text-emerald-400">
                        {o.status}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-sans text-[11px] text-slate-400 max-w-xs truncate">
                      {o.notes}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
