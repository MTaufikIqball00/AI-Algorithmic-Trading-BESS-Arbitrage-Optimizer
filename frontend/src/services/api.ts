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
} from "../types";

const API_BASE = "/api";

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    let errorDetail = response.statusText;
    try {
      const errJson = await response.json();
      errorDetail = errJson.error || errJson.detail || JSON.stringify(errJson);
    } catch {
      // ignore
    }
    throw new Error(`API Error (${response.status}): ${errorDetail}`);
  }

  return response.json();
}

export const api = {
  // System Health
  getHealth: () => fetchJson<SystemHealth>(`${API_BASE}/health`),

  // Market
  getMarketSummary: () => fetchJson<MarketSummary>(`${API_BASE}/market/summary`),
  getMarketPoints: (limit = 168, offset = 0) =>
    fetchJson<MarketPoint[]>(`${API_BASE}/market/points?limit=${limit}&offset=${offset}`),
  importMarketCsv: (csvContent: string) =>
    fetchJson<{ status: string; imported_records: number; message: string }>(
      `${API_BASE}/market/import`,
      {
        method: "POST",
        body: JSON.stringify({ csv_content: csvContent }),
      }
    ),

  // BESS
  getBessConfig: () => fetchJson<BatteryConfig>(`${API_BASE}/bess/config`),
  updateBessConfig: (config: BatteryConfig) =>
    fetchJson<{ status: string; message: string }>(`${API_BASE}/bess/config`, {
      method: "POST",
      body: JSON.stringify(config),
    }),
  getBessTelemetry: () => fetchJson<BatteryState>(`${API_BASE}/bess/telemetry`),
  resetBessTwin: () =>
    fetchJson<{ status: string; message: string }>(`${API_BASE}/bess/reset`, {
      method: "POST",
    }),

  // Forecast
  getForecastPredict: (horizon = 24) =>
    fetchJson<ForecastResponse>(`${API_BASE}/forecast/predict?horizon=${horizon}`),
  trainForecast: () =>
    fetchJson<{ status: string; message: string; data?: any }>(
      `${API_BASE}/forecast/train`,
      { method: "POST" }
    ),
  getForecastMetrics: () => fetchJson<ForecastMetrics>(`${API_BASE}/forecast/metrics`),

  // Strategy & Backtesting
  runBacktest: (payload: {
    strategy: "Idle" | "ThresholdHeuristic" | "ForecastHeuristic" | "PpoRl";
    start_index: number;
    end_index?: number;
    initial_soc: number;
    buy_threshold_pct?: number;
    sell_threshold_pct?: number;
  }) =>
    fetchJson<BacktestResponse>(`${API_BASE}/strategy/backtest`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getSensitivity: (param = "round_trip_efficiency") =>
    fetchJson<SensitivityResponse>(`${API_BASE}/strategy/sensitivity?param=${param}`),

  // Dispatch Planner
  getDispatchPlan: () => fetchJson<DispatchPlanResponse>(`${API_BASE}/dispatch/plan`),

  // Orders
  getOrders: () =>
    fetchJson<{ status: string; count: number; orders: PaperOrder[] }>(
      `${API_BASE}/orders`
    ),
  submitOrder: (order: {
    asset_id: string;
    side: "Charge" | "Discharge" | "Idle";
    power_mw: number;
    limit_price?: number;
  }) =>
    fetchJson<{ status: string; risk_passed: boolean; order?: PaperOrder }>(
      `${API_BASE}/orders/submit`,
      {
        method: "POST",
        body: JSON.stringify(order),
      }
    ),
  toggleKillSwitch: (active: boolean) =>
    fetchJson<{ status: string; kill_switch_active: boolean; message: string }>(
      `${API_BASE}/orders/killswitch`,
      {
        method: "POST",
        body: JSON.stringify({ active }),
      }
    ),

  // Audit
  getAuditLogs: () =>
    fetchJson<{ status: string; count: number; logs: AuditEvent[] }>(
      `${API_BASE}/audit/logs`
    ),
};
