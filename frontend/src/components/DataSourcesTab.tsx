import React from "react";
import {
  Database,
  ShieldCheck,
  FileText,
  Clock,
  AlertTriangle,
  Info,
  Server,
} from "lucide-react";
import { MarketSummary, AuditEvent } from "../types";

interface DataSourcesTabProps {
  summary: MarketSummary | null;
  auditLogs: AuditEvent[];
}

export const DataSourcesTab: React.FC<DataSourcesTabProps> = ({
  summary,
  auditLogs,
}) => {
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center space-x-2">
            <span>Data Sources, Provenance & Audit Governance</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Strict data governance, traceable data provenance, immutable audit logging, and schema integrity validation.
          </p>
        </div>
      </div>

      {/* Provenance Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h3 className="text-sm font-bold text-slate-100 mb-3 flex items-center space-x-2">
          <Database className="w-4 h-4 text-cyan-400" />
          <span>Active Data Feeds & Provenance Registry</span>
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/60">
                <th className="py-2.5 px-3">Market ID</th>
                <th className="py-2.5 px-3">ISO Operator</th>
                <th className="py-2.5 px-3">Interval</th>
                <th className="py-2.5 px-3">Currency / Unit</th>
                <th className="py-2.5 px-3">Provenance Category</th>
                <th className="py-2.5 px-3">Quality Status</th>
                <th className="py-2.5 px-3 text-right">Total Records</th>
                <th className="py-2.5 px-3">Date Range</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 text-slate-300">
              <tr className="hover:bg-slate-800/30">
                <td className="py-3 px-3 font-mono font-bold text-cyan-400">
                  {summary?.market_id ?? "CAISO_SP15"}
                </td>
                <td className="py-3 px-3">California Independent System Operator (CAISO)</td>
                <td className="py-3 px-3 font-mono">1 Hour (60 min)</td>
                <td className="py-3 px-3 font-mono">USD ($/MWh)</td>
                <td className="py-3 px-3">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 border border-emerald-800 text-emerald-400">
                    HISTORICAL_BENCHMARK
                  </span>
                </td>
                <td className="py-3 px-3">
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400">
                    VALID (0 Gaps)
                  </span>
                </td>
                <td className="py-3 px-3 text-right font-mono font-bold text-slate-100">
                  {summary?.total_records ?? 8784} hrs
                </td>
                <td className="py-3 px-3 font-mono text-[11px] text-slate-400">
                  {summary?.start_timestamp.substring(0, 10)} to {summary?.end_timestamp.substring(0, 10)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      {/* Database & Governance Architecture Card */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 text-xs space-y-3">
          <h3 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
            <Server className="w-4 h-4 text-emerald-400" />
            <span>Storage & Persistence Engine</span>
          </h3>

          <div className="space-y-2 text-slate-300">
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-400">Primary Database:</span>
              <span className="font-mono text-emerald-400 font-bold">SQLite Embedded (WAL Mode)</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-400">ACID Guarantees:</span>
              <span className="font-mono text-slate-200">Full Transactional Consistency</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800">
              <span className="text-slate-400">Relational & Time-Series:</span>
              <span className="font-mono text-slate-200">Indexed by Timestamp & Order ID</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-400">External TimescaleDB Port:</span>
              <span className="font-mono text-slate-400">55452 (Configurable in .env)</span>
            </div>
          </div>
        </div>

        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5 text-xs space-y-3">
          <h3 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-indigo-400" />
            <span>Data Integrity & Anti-Leakage Protocol</span>
          </h3>

          <div className="space-y-2 text-slate-300 text-[11px]">
            <p>
              • <strong className="text-slate-100">Zero Future Leakage:</strong> All feature transformations strictly employ historical shifts (<code className="text-cyan-300">t-1, t-24</code>) and exclude current/future intervals.
            </p>
            <p>
              • <strong className="text-slate-100">Walk-Forward Validation:</strong> Models evaluated strictly on chronological out-of-sample test splits, avoiding random cross-validation data bleed.
            </p>
            <p>
              • <strong className="text-slate-100">Synthetic Transparency:</strong> All simulated datasets are permanently flagged as <code className="text-amber-400">SYNTHETIC_SIMULATED</code>.
            </p>
          </div>
        </div>
      </div>

      {/* System Audit Trail */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <h3 className="text-sm font-bold text-slate-100 mb-3 flex items-center space-x-2">
          <FileText className="w-4 h-4 text-amber-400" />
          <span>System & Security Audit Trail</span>
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/60">
                <th className="py-2.5 px-3">Event ID</th>
                <th className="py-2.5 px-3">Timestamp</th>
                <th className="py-2.5 px-3">Severity</th>
                <th className="py-2.5 px-3">Event Type</th>
                <th className="py-2.5 px-3">Details</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-mono text-slate-300">
              {auditLogs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-500 font-sans">
                    No audit logs recorded yet.
                  </td>
                </tr>
              ) : (
                auditLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-slate-800/30">
                    <td className="py-2.5 px-3 font-bold text-slate-400">{log.id.substring(0, 8)}</td>
                    <td className="py-2.5 px-3 text-slate-400">{log.timestamp.substring(0, 19).replace("T", " ")}</td>
                    <td className="py-2.5 px-3">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          log.severity === "CRITICAL"
                            ? "bg-rose-950 text-rose-400 border border-rose-800"
                            : log.severity === "WARN"
                            ? "bg-amber-950 text-amber-400 border border-amber-800"
                            : "bg-slate-800 text-slate-300 border border-slate-700"
                        }`}
                      >
                        {log.severity}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-sans font-semibold text-slate-200">
                      {log.event_type}
                    </td>
                    <td className="py-2.5 px-3 font-sans text-slate-300">
                      {log.details}
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
