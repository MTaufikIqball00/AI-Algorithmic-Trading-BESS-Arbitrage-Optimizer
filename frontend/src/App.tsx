import React, { useState, useEffect, useCallback } from "react";
import { Header } from "./components/Header";
import { OverviewTab } from "./components/OverviewTab";
import { MarketTab } from "./components/MarketTab";
import { BatteryTwinTab } from "./components/BatteryTwinTab";
import { StrategyLabTab } from "./components/StrategyLabTab";
import { DispatchPlannerTab } from "./components/DispatchPlannerTab";
import { BacktestingTab } from "./components/BacktestingTab";
import { OrdersTab } from "./components/OrdersTab";
import { DataSourcesTab } from "./components/DataSourcesTab";
import { api } from "./services/api";
import {
  SystemHealth,
  MarketSummary,
  MarketPoint,
  BatteryConfig,
  BatteryState,
  ForecastResponse,
  ForecastMetrics,
  BacktestResponse,
  SensitivityResponse,
  DispatchPlanResponse,
  PaperOrder,
  AuditEvent,
} from "./types";

export function App() {
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [summary, setSummary] = useState<MarketSummary | null>(null);
  const [marketPoints, setMarketPoints] = useState<MarketPoint[]>([]);
  const [config, setConfig] = useState<BatteryConfig | null>(null);
  const [telemetry, setTelemetry] = useState<BatteryState | null>(null);
  const [dispatchPlan, setDispatchPlan] = useState<DispatchPlanResponse | null>(null);
  const [forecast, setForecast] = useState<ForecastResponse | null>(null);
  const [forecastMetrics, setForecastMetrics] = useState<ForecastMetrics | null>(null);
  const [backtestResult, setBacktestResult] = useState<BacktestResponse | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityResponse | null>(null);
  const [orders, setOrders] = useState<PaperOrder[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const fetchInitialData = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMsg(null);

      const [
        h,
        sum,
        pts,
        cfg,
        tel,
        plan,
        fc,
        fcMetrics,
        ordResp,
        auditResp,
        sensResp,
      ] = await Promise.all([
        api.getHealth().catch(() => null),
        api.getMarketSummary().catch(() => null),
        api.getMarketPoints(168, 0).catch(() => []),
        api.getBessConfig().catch(() => null),
        api.getBessTelemetry().catch(() => null),
        api.getDispatchPlan().catch(() => null),
        api.getForecastPredict(24).catch(() => null),
        api.getForecastMetrics().catch(() => null),
        api.getOrders().catch(() => ({ status: "err", count: 0, orders: [] })),
        api.getAuditLogs().catch(() => ({ status: "err", count: 0, logs: [] })),
        api.getSensitivity("round_trip_efficiency").catch(() => null),
      ]);

      if (h) setHealth(h);
      if (sum) setSummary(sum);
      if (pts) setMarketPoints(pts);
      if (cfg) setConfig(cfg);
      if (tel) setTelemetry(tel);
      if (plan) setDispatchPlan(plan);
      if (fc) setForecast(fc);
      if (fcMetrics) setForecastMetrics(fcMetrics);
      if (ordResp?.orders) setOrders(ordResp.orders);
      if (auditResp?.logs) setAuditLogs(auditResp.logs);
      if (sensResp) setSensitivity(sensResp);

      // Trigger automatic initial backtest to populate charts
      api
        .runBacktest({
          strategy: "ThresholdHeuristic",
          start_index: 0,
          end_index: 720,
          initial_soc: 0.50,
          buy_threshold_pct: 25.0,
          sell_threshold_pct: 75.0,
        })
        .then((bt) => setBacktestResult(bt))
        .catch(() => {});
    } catch (e: any) {
      setErrorMsg(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchInitialData();
    // Poll telemetry every 10 seconds
    const interval = setInterval(() => {
      api.getBessTelemetry().then((tel) => setTelemetry(tel)).catch(() => {});
      api.getHealth().then((h) => setHealth(h)).catch(() => {});
    }, 10000);
    return () => clearInterval(interval);
  }, [fetchInitialData]);

  // Action Handlers
  const handleToggleKillSwitch = async (active: boolean) => {
    try {
      const resp = await api.toggleKillSwitch(active);
      if (health) {
        setHealth({
          ...health,
          risk_controls: {
            ...health.risk_controls,
            emergency_kill_switch: resp.kill_switch_active,
          },
        });
      }
      const logs = await api.getAuditLogs();
      setAuditLogs(logs.logs);
    } catch (e: any) {
      alert(`Kill-switch error: ${e.message}`);
    }
  };

  const handleTrainModel = async () => {
    await api.trainForecast();
    const [fc, metrics] = await Promise.all([
      api.getForecastPredict(24),
      api.getForecastMetrics(),
    ]);
    setForecast(fc);
    setForecastMetrics(metrics);
  };

  const handleImportCsv = async (csvContent: string) => {
    await api.importMarketCsv(csvContent);
    await fetchInitialData();
    try {
      await handleTrainModel();
    } catch (e) {
      console.warn("Notice on auto-train after import:", e);
    }
  };

  const handleUpdateConfig = async (newCfg: BatteryConfig) => {
    await api.updateBessConfig(newCfg);
    setConfig(newCfg);
    const plan = await api.getDispatchPlan();
    setDispatchPlan(plan);
  };

  const handleResetTwin = async () => {
    await api.resetBessTwin();
    const tel = await api.getBessTelemetry();
    setTelemetry(tel);
  };

  const handleRunBacktest = async (
    strategy: "Idle" | "ThresholdHeuristic" | "ForecastHeuristic" | "PpoRl",
    startIdx: number,
    endIdx?: number
  ) => {
    const res = await api.runBacktest({
      strategy,
      start_index: startIdx,
      end_index: endIdx,
      initial_soc: 0.50,
      buy_threshold_pct: 25.0,
      sell_threshold_pct: 75.0,
    });
    setBacktestResult(res);
  };

  const handleFetchSensitivity = async (param: string) => {
    const res = await api.getSensitivity(param);
    setSensitivity(res);
  };

  const handleSubmitOrder = async (order: {
    asset_id: string;
    side: "Charge" | "Discharge" | "Idle";
    power_mw: number;
    limit_price?: number;
  }) => {
    await api.submitOrder(order);
    const [ordResp, tel, auditResp] = await Promise.all([
      api.getOrders(),
      api.getBessTelemetry(),
      api.getAuditLogs(),
    ]);
    setOrders(ordResp.orders);
    setTelemetry(tel);
    setAuditLogs(auditResp.logs);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-cyan-500 selection:text-slate-950">
      <Header
        health={health}
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onToggleKillSwitch={handleToggleKillSwitch}
      />

      <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 lg:p-8">
        {errorMsg && (
          <div className="mb-6 p-4 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 text-xs">
            <span className="font-bold">Backend Connection Notice: </span>
            {errorMsg} (Please ensure backend is started on port 8230).
          </div>
        )}

        {loading ? (
          <div className="h-96 flex flex-col items-center justify-center space-y-3">
            <div className="w-8 h-8 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-slate-400">Loading BESS Optimizer Data...</p>
          </div>
        ) : (
          <>
            {activeTab === "overview" && (
              <OverviewTab
                summary={summary}
                telemetry={telemetry}
                config={config}
                dispatchPlan={dispatchPlan}
                onRefresh={fetchInitialData}
                onTriggerBacktest={() => setActiveTab("backtesting")}
                onResetTwin={handleResetTwin}
              />
            )}

            {activeTab === "market" && (
              <MarketTab
                marketPoints={marketPoints}
                forecast={forecast}
                metrics={forecastMetrics}
                onTrainModel={handleTrainModel}
                onImportCsv={handleImportCsv}
              />
            )}

            {activeTab === "battery" && (
              <BatteryTwinTab
                config={config}
                telemetry={telemetry}
                onUpdateConfig={handleUpdateConfig}
                onResetTwin={handleResetTwin}
              />
            )}

            {activeTab === "strategy" && <StrategyLabTab />}

            {activeTab === "dispatch" && (
              <DispatchPlannerTab dispatchPlan={dispatchPlan} />
            )}

            {activeTab === "backtesting" && (
              <BacktestingTab
                backtestResult={backtestResult}
                sensitivity={sensitivity}
                onRunBacktest={handleRunBacktest}
                onFetchSensitivity={handleFetchSensitivity}
              />
            )}

            {activeTab === "orders" && (
              <OrdersTab
                orders={orders}
                config={config}
                telemetry={telemetry}
                killSwitchActive={health?.risk_controls.emergency_kill_switch ?? false}
                onSubmitOrder={handleSubmitOrder}
                onToggleKillSwitch={handleToggleKillSwitch}
              />
            )}

            {activeTab === "datasources" && (
              <DataSourcesTab summary={summary} auditLogs={auditLogs} />
            )}
          </>
        )}
      </main>

      <footer className="border-t border-slate-800 bg-slate-900/60 py-3 text-center text-xs text-slate-500">
        AI Algorithmic Trading & BESS Arbitrage Optimizer • Production-Grade Energy Trading Terminal
      </footer>
    </div>
  );
}

export default App;
