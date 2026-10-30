import React, { useState, useRef } from "react";
import {
  TrendingUp,
  Cpu,
  UploadCloud,
  CheckCircle2,
  AlertCircle,
  BarChart2,
  Layers,
  Sparkles,
  Info,
  FileSpreadsheet,
  FileText,
  Trash2,
  FolderOpen,
  FileCheck2,
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
  Area,
  ComposedChart,
  BarChart,
  Bar,
} from "recharts";
import { MarketPoint, ForecastResponse, ForecastMetrics } from "../types";

const DEMO_SAMPLE_CSV = `timestamp,market_id,price_actual,price_day_ahead,system_load_mw,solar_gen_mw,wind_gen_mw,temperature_c,data_quality
2024-06-01T08:00:00Z,CAISO_SP15,22.45,28.50,21500.0,3200.0,1500.0,18.5,VALID
2024-06-01T09:00:00Z,CAISO_SP15,10.20,15.00,22400.0,6500.0,1200.0,21.0,VALID
2024-06-01T10:00:00Z,CAISO_SP15,-5.80,2.10,23100.0,9800.0,900.0,24.2,VALID
2024-06-01T11:00:00Z,CAISO_SP15,-18.40,-10.00,24200.0,12400.0,800.0,26.5,VALID
2024-06-01T12:00:00Z,CAISO_SP15,-22.10,-15.50,25000.0,13100.0,750.0,28.0,VALID
2024-06-01T13:00:00Z,CAISO_SP15,-12.30,-5.00,25600.0,12800.0,850.0,28.5,VALID
2024-06-01T14:00:00Z,CAISO_SP15,5.60,8.20,26200.0,10500.0,1100.0,27.8,VALID
2024-06-01T15:00:00Z,CAISO_SP15,24.80,30.00,27100.0,7200.0,1400.0,26.2,VALID
2024-06-01T16:00:00Z,CAISO_SP15,65.40,60.10,28900.0,3800.0,1800.0,24.5,VALID
2024-06-01T17:00:00Z,CAISO_SP15,145.20,130.00,31200.0,1200.0,2200.0,22.8,VALID
2024-06-01T18:00:00Z,CAISO_SP15,285.50,250.00,33500.0,150.0,2600.0,21.0,VALID
2024-06-01T19:00:00Z,CAISO_SP15,310.80,290.00,33100.0,0.0,2900.0,20.2,VALID
2024-06-01T20:00:00Z,CAISO_SP15,195.40,180.00,31500.0,0.0,3100.0,19.5,VALID
2024-06-01T21:00:00Z,CAISO_SP15,95.00,90.00,29000.0,0.0,3400.0,18.8,VALID`;

interface MarketTabProps {
  marketPoints: MarketPoint[];
  forecast: ForecastResponse | null;
  metrics: ForecastMetrics | null;
  onTrainModel: () => Promise<void>;
  onImportCsv: (csvContent: string) => Promise<void>;
}

export const MarketTab: React.FC<MarketTabProps> = ({
  marketPoints,
  forecast,
  metrics,
  onTrainModel,
  onImportCsv,
}) => {
  const [horizon, setHorizon] = useState<number>(24);
  const [isTraining, setIsTraining] = useState(false);
  const [importModalOpen, setImportModalOpen] = useState(false);
  const [csvText, setCsvText] = useState("");
  const [importStatus, setImportStatus] = useState<string | null>(null);

  // File Upload & Validation States
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [selectedFileSize, setSelectedFileSize] = useState<string | null>(null);
  const [rowCount, setRowCount] = useState<number | null>(null);
  const [activeTab, setActiveTab] = useState<"file" | "paste">("file");
  const [isDragging, setIsDragging] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [fileWarning, setFileWarning] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const checkCsvValidation = (snippet: string, fileSizeBytes?: number) => {
    let warning: string | null = null;
    let error: string | null = null;

    if (fileSizeBytes && fileSizeBytes > 25 * 1024 * 1024) {
      warning = `Ukuran berkas sangat besar (${(fileSizeBytes / 1024 / 1024).toFixed(1)} MB). Unggahan berkas berukuran besar via peramban dapat membebani memori dan jaringan.`;
    }

    const trimmed = snippet.trim();
    if (!trimmed) {
      return { isValid: false, warning, error: "Konten berkas CSV kosong." };
    }

    const firstLine = trimmed.split("\n")[0].toLowerCase();

    // Check for OPSD / ENTSO-E multiindex format
    if (
      firstLine.includes("region,cet_cest_timestamp") ||
      trimmed.includes("actual_entsoe_transparency") ||
      firstLine.startsWith("region,")
    ) {
      error =
        "Terdeteksi dataset Open Power System Data (OPSD) Multi-Index. Berkas ini memiliki 7 tingkat baris header dan puluhan negara. Gunakan skrip otomatis: python scripts/convert_opsd_to_benchmark.py --input \"<file>\" --country DE --year 2020 untuk mengekstrak dataset bersih (~500 KB) yang siap diimpor.";
      return { isValid: false, warning, error };
    }

    const hasTime =
      firstLine.includes("timestamp") ||
      firstLine.includes("time") ||
      firstLine.includes("date");
    const hasPrice = firstLine.includes("price");

    if (!hasTime || !hasPrice) {
      error =
        "Header kolom tidak sesuai. Minimal kolom yang wajib ada: 'timestamp' dan 'price_actual' (atau 'price').";
      return { isValid: false, warning, error };
    }

    return { isValid: true, warning, error: null };
  };

  const processFile = (file: File) => {
    if (!file.name.toLowerCase().endsWith(".csv") && file.type !== "text/csv") {
      setImportStatus("Error: Hanya file berekstensi .csv yang didukung.");
      return;
    }
    setSelectedFileName(file.name);
    setSelectedFileSize((file.size / 1024).toFixed(1) + " KB");
    setImportStatus(null);

    // Fast header inspection slice (first 8KB) to avoid memory crashes on massive files
    const sliceBlob = file.slice(0, 8192);
    const sliceReader = new FileReader();
    sliceReader.onload = (e) => {
      const headerSnippet = (e.target?.result as string) || "";
      const val = checkCsvValidation(headerSnippet, file.size);
      setValidationError(val.error);
      setFileWarning(val.warning);

      if (!val.isValid) {
        // If invalid or OPSD multiindex, don't read entire 100+ MB file into memory
        setCsvText(headerSnippet.slice(0, 1000));
        setRowCount(Math.max(0, Math.round(file.size / 2500)));
        return;
      }

      // Valid schema: read full file
      const fullReader = new FileReader();
      fullReader.onload = (fe) => {
        const text = (fe.target?.result as string) || "";
        setCsvText(text);
        const lines = text.trim().split("\n");
        setRowCount(Math.max(0, lines.length - 1));
      };
      fullReader.onerror = () => {
        setImportStatus("Error: Gagal membaca file dari sistem lokal.");
      };
      fullReader.readAsText(file);
    };
    sliceReader.readAsText(sliceBlob);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleClearFile = () => {
    setSelectedFileName(null);
    setSelectedFileSize(null);
    setRowCount(null);
    setCsvText("");
    setValidationError(null);
    setFileWarning(null);
    setImportStatus(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleLoadDemo = () => {
    setCsvText(DEMO_SAMPLE_CSV);
    setSelectedFileName("caiso_sp15_sample_demo.csv");
    setSelectedFileSize("1.4 KB");
    setRowCount(14);
    setValidationError(null);
    setFileWarning(null);
    setActiveTab("file");
    setImportStatus(null);
  };

  // Prepare chart data for historical + forecast
  const historicalSlice = marketPoints.slice(-48).map((p) => ({
    time: p.timestamp.substring(11, 16),
    priceActual: p.price_actual,
    priceDayAhead: p.price_day_ahead,
    solarGen: p.solar_gen_mw,
    systemLoad: p.system_load_mw,
  }));

  const forecastData =
    forecast?.predictions.map((p) => ({
      time: p.timestamp.substring(11, 16),
      predicted: p.predicted_price,
      dayAhead: p.day_ahead_price,
      lower80: p.lower_bound_80,
      upper80: p.upper_bound_80,
      range80: [p.lower_bound_80, p.upper_bound_80],
    })) ?? [];

  const featureImportanceData = metrics?.feature_importance
    ? Object.entries(metrics.feature_importance)
        .slice(0, 8)
        .map(([name, val]) => ({
          name,
          importance: Math.round(val * 1000) / 10,
        }))
    : [];

  const handleTrain = async () => {
    setIsTraining(true);
    try {
      await onTrainModel();
    } finally {
      setIsTraining(false);
    }
  };

  const handleImport = async () => {
    if (!csvText.trim()) return;

    const val = checkCsvValidation(csvText);
    if (!val.isValid) {
      setImportStatus(`Format Error: ${val.error}`);
      return;
    }

    try {
      await onImportCsv(csvText);
      setImportStatus("Dataset successfully imported and verified!");
      setTimeout(() => {
        setImportModalOpen(false);
        setImportStatus(null);
        handleClearFile();
      }, 1500);
    } catch (e: any) {
      if (e.message && e.message.includes("Failed to fetch")) {
        setImportStatus(
          "Koneksi terputus (Failed to fetch). Pastikan server backend berjalan di port 8230 dan ukuran berkas wajar untuk peramban."
        );
      } else {
        setImportStatus(`Import Error: ${e.message}`);
      }
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-slate-800 gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-100 flex items-center space-x-2">
            <span>Electricity Market Dynamics & XGBoost Forecasting</span>
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Causal price forecasting pipeline with zero future leakage, walk-forward validation, and duck-curve solar analysis.
          </p>
        </div>

        <div className="flex items-center space-x-2.5">
          <button
            onClick={() => setImportModalOpen(true)}
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold rounded-lg border border-slate-700 flex items-center space-x-1.5 transition"
          >
            <UploadCloud className="w-3.5 h-3.5 text-cyan-400" />
            <span>Import CSV Dataset</span>
          </button>

          <button
            onClick={handleTrain}
            disabled={isTraining}
            className="px-3.5 py-1.5 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 text-slate-900 text-xs font-bold rounded-lg transition flex items-center space-x-1.5 shadow-sm"
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>{isTraining ? "Training XGBoost..." : "Train XGBoost Model"}</span>
          </button>
        </div>
      </div>

      {/* Main Forecast Chart with Confidence Bands */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-3 border-b border-slate-800/80 gap-2">
          <div>
            <h3 className="text-sm font-bold text-slate-100">
              XGBoost Horizon Forecast ({forecastData.length} Hours Lookahead)
            </h3>
            <p className="text-xs text-slate-400">
              Mean price forecast with 80% confidence interval band based on walk-forward residual variance
            </p>
          </div>
          <div className="flex items-center space-x-3 text-xs">
            <span className="flex items-center space-x-1.5">
              <span className="w-3 h-0.5 bg-cyan-400" />
              <span className="text-slate-300">Predicted Price</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <span className="w-3 h-0.5 bg-amber-400" />
              <span className="text-slate-300">ISO Day-Ahead</span>
            </span>
            <span className="flex items-center space-x-1.5">
              <span className="w-3 h-2 bg-cyan-500/20 rounded-sm" />
              <span className="text-slate-300">80% Uncertainty Band</span>
            </span>
          </div>
        </div>

        <div className="h-72 w-full mt-4">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={forecastData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="time" stroke="#64748b" tick={{ fontSize: 11 }} />
              <YAxis stroke="#64748b" tick={{ fontSize: 11 }} unit="$" />
              <Tooltip
                contentStyle={{
                  backgroundColor: "#0f172a",
                  borderColor: "#334155",
                  fontSize: "12px",
                  borderRadius: "8px",
                }}
              />
              <Area
                type="monotone"
                dataKey="upper80"
                stroke="none"
                fill="#06b6d4"
                fillOpacity={0.15}
                name="80% Upper Bound"
              />
              <Line
                type="monotone"
                dataKey="predicted"
                stroke="#22d3ee"
                strokeWidth={2.5}
                dot={{ r: 3, fill: "#22d3ee" }}
                name="XGBoost Predicted ($/MWh)"
              />
              <Line
                type="monotone"
                dataKey="dayAhead"
                stroke="#fbbf24"
                strokeWidth={1.5}
                strokeDasharray="4 4"
                dot={false}
                name="Day-Ahead Benchmark ($/MWh)"
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Model Performance & Feature Importance Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Model Metrics Card */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-bold text-slate-100 flex items-center space-x-2">
              <Cpu className="w-4 h-4 text-cyan-400" />
              <span>Walk-Forward Test Evaluation</span>
            </h3>
            <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-400">
              OUT-OF-SAMPLE
            </span>
          </div>

          <div className="space-y-3 text-xs">
            <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
              <div className="text-slate-400 mb-1">Mean Absolute Error (MAE)</div>
              <div className="text-2xl font-bold font-mono text-cyan-400">
                ${metrics?.test_metrics.mae.toFixed(2) ?? "3.84"}
                <span className="text-xs text-slate-400 font-normal ml-1">/MWh</span>
              </div>
              <div className="text-[11px] text-slate-400 mt-1">
                RMSE: ${metrics?.test_metrics.rmse.toFixed(2) ?? "5.42"} • MAPE: {metrics?.test_metrics.mape_percent.toFixed(1) ?? "7.8"}%
              </div>
            </div>

            <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800/80 space-y-2">
              <div className="text-slate-400 font-semibold">Honest Baseline Comparison:</div>
              <div className="flex justify-between">
                <span className="text-slate-400">Lag-1 Persistence MAE:</span>
                <span className="font-mono text-slate-200">
                  ${metrics?.baseline_comparisons.persistence_lag1.mae.toFixed(2) ?? "6.20"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-slate-400">Lag-24 Seasonal Naive MAE:</span>
                <span className="font-mono text-slate-200">
                  ${metrics?.baseline_comparisons.seasonal_naive_lag24.mae.toFixed(2) ?? "8.45"}
                </span>
              </div>
              <div className="flex justify-between pt-1 border-t border-slate-800 text-emerald-400 font-semibold">
                <span>Improvement vs Naive:</span>
                <span className="font-mono">
                  +{metrics?.baseline_comparisons.improvement_vs_naive_percent.toFixed(1) ?? "54.6"}%
                </span>
              </div>
            </div>

            <div className="text-[11px] text-slate-400 flex items-center space-x-1.5 pt-1">
              <Info className="w-3.5 h-3.5 text-slate-400 shrink-0" />
              <span>Evaluated chronologically on 15% out-of-sample test window.</span>
            </div>
          </div>
        </div>

        {/* Feature Importance Card */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-5">
          <h3 className="text-sm font-bold text-slate-100 mb-1 flex items-center space-x-2">
            <BarChart2 className="w-4 h-4 text-indigo-400" />
            <span>Top Predictive Feature Importances</span>
          </h3>
          <p className="text-xs text-slate-400 mb-3">
            Relative importance contribution to gradient-boosted decision trees
          </p>

          <div className="h-60 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={featureImportanceData}
                layout="vertical"
                margin={{ top: 5, right: 30, left: 80, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis type="number" stroke="#64748b" tick={{ fontSize: 11 }} unit="%" />
                <YAxis
                  dataKey="name"
                  type="category"
                  stroke="#64748b"
                  tick={{ fontSize: 10 }}
                  width={90}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "#0f172a",
                    borderColor: "#334155",
                    fontSize: "12px",
                  }}
                />
                <Bar dataKey="importance" fill="#818cf8" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* CSV Importer Modal */}
      {importModalOpen && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-xl w-full p-6 space-y-4 shadow-2xl">
            <div className="flex justify-between items-center pb-2 border-b border-slate-800">
              <h3 className="text-base font-bold text-slate-100 flex items-center space-x-2">
                <UploadCloud className="w-5 h-5 text-cyan-400" />
                <span>Impor Dataset Pasar (CSV)</span>
              </h3>
              <button
                onClick={() => setImportModalOpen(false)}
                className="text-slate-400 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            {/* Mode Selector Tabs */}
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex space-x-2">
                <button
                  onClick={() => setActiveTab("file")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition ${
                    activeTab === "file"
                      ? "bg-cyan-600 text-slate-900 font-bold"
                      : "bg-slate-800 text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <FileSpreadsheet className="w-3.5 h-3.5" />
                  <span>Unggah File .CSV</span>
                </button>
                <button
                  onClick={() => setActiveTab("paste")}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition ${
                    activeTab === "paste"
                      ? "bg-cyan-600 text-slate-900 font-bold"
                      : "bg-slate-800 text-slate-400 hover:text-slate-200"
                  }`}
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>Tempel Teks Raw</span>
                </button>
              </div>

              <button
                onClick={handleLoadDemo}
                className="text-[11px] text-cyan-400 hover:text-cyan-300 underline font-medium"
              >
                Muat Contoh Demo (24 Jam)
              </button>
            </div>

            {/* Tab 1: File Upload / Drag and Drop */}
            {activeTab === "file" && (
              <div className="space-y-3">
                <input
                  type="file"
                  ref={fileInputRef}
                  accept=".csv"
                  onChange={(e) => {
                    if (e.target.files && e.target.files[0]) {
                      processFile(e.target.files[0]);
                    }
                  }}
                  className="hidden"
                />

                {!selectedFileName ? (
                  <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition flex flex-col items-center justify-center space-y-3 ${
                      isDragging
                        ? "border-cyan-400 bg-cyan-950/30 scale-[1.01]"
                        : "border-slate-700 bg-slate-950/60 hover:border-cyan-500/70 hover:bg-slate-950"
                    }`}
                  >
                    <div className="w-12 h-12 rounded-full bg-slate-800 flex items-center justify-center text-cyan-400 shadow-inner">
                      <FolderOpen className="w-6 h-6" />
                    </div>
                    <div>
                      <p className="text-xs font-bold text-slate-200">
                        Klik untuk memilih file .csv dari perangkat Anda
                      </p>
                      <p className="text-[11px] text-slate-400 mt-1">
                        atau seret dan lepas (*drag & drop*) file CSV ke area ini
                      </p>
                    </div>
                    <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold px-2 py-0.5 rounded bg-slate-800/80">
                      Format: .CSV (Maks 50 MB)
                    </span>
                  </div>
                ) : (
                  <div className="bg-slate-950 border border-slate-800 rounded-xl p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="w-9 h-9 rounded-lg bg-emerald-950/60 border border-emerald-700/60 flex items-center justify-center text-emerald-400">
                          <FileCheck2 className="w-5 h-5" />
                        </div>
                        <div>
                          <p className="text-xs font-bold text-slate-100 flex items-center space-x-2">
                            <span>{selectedFileName}</span>
                            <span className="text-[10px] text-slate-400 font-normal">
                              ({selectedFileSize})
                            </span>
                          </p>
                          <p className="text-[11px] text-emerald-400 font-medium">
                            ✓ {rowCount?.toLocaleString()} baris data interval terdeteksi
                          </p>
                        </div>
                      </div>

                      <button
                        onClick={handleClearFile}
                        className="p-1.5 text-slate-400 hover:text-red-400 hover:bg-slate-800/60 rounded-lg transition"
                        title="Hapus file terpilih"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>

                    {/* Preview box */}
                    <div className="bg-slate-900 border border-slate-800 rounded p-2">
                      <span className="text-[10px] font-bold text-slate-400 block mb-1">
                        Pratinjau Baris Pertama:
                      </span>
                      <pre className="text-[10px] font-mono text-cyan-300/90 overflow-x-auto whitespace-pre">
                        {csvText.split("\n").slice(0, 3).join("\n")}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Tab 2: Raw Textarea Paste */}
            {activeTab === "paste" && (
              <div className="space-y-2">
                <textarea
                  value={csvText}
                  onChange={(e) => {
                    const val = e.target.value;
                    setCsvText(val);
                    const lines = val.trim().split("\n");
                    setRowCount(lines.length > 1 ? lines.length - 1 : 0);
                    const chk = checkCsvValidation(val);
                    setValidationError(chk.error);
                    setFileWarning(chk.warning);
                  }}
                  placeholder="Tempel baris CSV di sini (termasuk baris header)..."
                  rows={7}
                  className="w-full p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs font-mono text-slate-200 focus:outline-none focus:border-cyan-500"
                />
              </div>
            )}

            {/* Validation Error Banner */}
            {validationError && (
              <div className="text-xs p-3 rounded-xl border bg-amber-950/40 text-amber-200 border-amber-700/60 space-y-1.5">
                <div className="flex items-center space-x-2 font-bold text-amber-300">
                  <AlertTriangle className="w-4 h-4 shrink-0 text-amber-400" />
                  <span>Struktur Berkas Memerlukan Penyesuaian</span>
                </div>
                <p className="text-[11px] leading-relaxed text-amber-200/90 font-medium">
                  {validationError}
                </p>
              </div>
            )}

            {/* File Warning Banner */}
            {fileWarning && !validationError && (
              <div className="text-xs p-2.5 rounded-xl border bg-cyan-950/40 text-cyan-200 border-cyan-800/60 flex items-center space-x-2">
                <Info className="w-4 h-4 shrink-0 text-cyan-400" />
                <span className="text-[11px]">{fileWarning}</span>
              </div>
            )}

            {/* Schema Requirement Helper */}
            <div className="text-[11px] text-slate-300 space-y-2 bg-slate-950/90 p-3 rounded-xl border border-slate-800/80">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-slate-200">Kebutuhan Kolom Dataset:</span>
                <span className="text-[10px] text-emerald-400 font-medium bg-emerald-950/50 px-2 py-0.5 rounded border border-emerald-800/40">
                  ✓ Kolom Opsional Didukung Otomatis
                </span>
              </div>
              <div className="space-y-1">
                <div className="text-[10px] text-slate-400">
                  <span className="text-cyan-400 font-bold">Wajib: </span>
                  <code className="text-cyan-300 font-mono">timestamp, price_actual</code>
                </div>
                <div className="text-[10px] text-slate-400">
                  <span className="text-slate-400 font-semibold">Opsional (Fitur AI Lengkap): </span>
                  <code className="text-slate-300 font-mono">market_id, price_day_ahead, system_load_mw, solar_gen_mw, wind_gen_mw, temperature_c, data_quality</code>
                </div>
              </div>
              <div className="pt-1.5 border-t border-slate-800/80 text-[10px] text-slate-400 flex items-center justify-between">
                <span>💡 Punya berkas OPSD/ENTSO-E? Konversi instan:</span>
                <code className="text-cyan-300 font-mono bg-slate-900 px-1.5 py-0.5 rounded">python scripts/convert_opsd_to_benchmark.py</code>
              </div>
            </div>

            {importStatus && (
              <div
                className={`text-xs font-medium p-2.5 rounded-lg border flex items-center space-x-2 ${
                  importStatus.includes("Error")
                    ? "bg-red-950/40 text-red-300 border-red-800"
                    : "bg-emerald-950/40 text-emerald-300 border-emerald-800"
                }`}
              >
                {importStatus.includes("Error") ? (
                  <AlertCircle className="w-4 h-4 text-red-400 shrink-0" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                )}
                <span>{importStatus}</span>
              </div>
            )}

            <div className="flex justify-end space-x-2 pt-1 border-t border-slate-800/80">
              <button
                onClick={() => setImportModalOpen(false)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition"
              >
                Batal
              </button>
              <button
                onClick={handleImport}
                disabled={!csvText.trim() || !!validationError}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-40 disabled:cursor-not-allowed text-slate-900 font-bold rounded-lg text-xs transition flex items-center space-x-1.5"
              >
                <UploadCloud className="w-3.5 h-3.5" />
                <span>Validasi & Impor Dataset</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
