# AI Algorithmic Trading & BESS Arbitrage Optimizer

[![Rust](https://img.shields.io/badge/Rust-1.80%2B-orange?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![Axum](https://img.shields.io/badge/Axum-0.7-blue?logo=rust)](https://github.com/tokio-rs/axum)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0%2B-green?logo=xgboost)](https://xgboost.readthedocs.io/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-v4-38B2AC?logo=tailwind-css&logoColor=white)](https://tailwindcss.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Platform terintegrasi skala industri untuk **Optimasi Arbitrase & Algorithmic Trading Battery Energy Storage System (BESS)** pada pasar listrik grosir (*wholesale electricity markets* seperti CAISO, ERCOT, dan NEM).

Sistem ini menjembatani batas fisik elektrokimia baterai nyata, peramalan harga listrik (*price forecasting*) dengan Machine Learning, optimasi *dispatch* berbasis Reinforcement Learning, mesin *backtesting* deterministik berkecepatan tinggi, manajemen risiko *pre-trade*, dan terminal perdagangan interaktif berbasis web.

---

## Daftar Isi
1. [Gambaran Umum & Nilai Utama](#1-gambaran-umum--nilai-utama)
2. [Arsitektur Sistem](#2-arsitektur-sistem)
3. [Pemodelan Fisika BESS & Ketelitian Matematis](#3-pemodelan-fisika-bess--ketelitian-matematis)
4. [Kecerdasan Buatan & Machine Learning](#4-kecerdasan-buatan--machine-learning)
5. [Terminal Trading Frontend](#5-terminal-trading-frontend)
6. [Tata Kelola Data & Benchmark CAISO 2024](#6-tata-kelola-data--benchmark-caiso-2024)
7. [Spesifikasi API](#7-spesifikasi-api)
8. [Panduan Instalasi & Menjalankan Aplikasi](#8-panduan-instalasi--menjalankan-aplikasi)
9. [Verifikasi Pengujian & Quality Gates](#9-verifikasi-pengujian--quality-gates)
10. [Manajemen Risiko & Keamanan Operasional](#10-manajemen-risiko--keamanan-operasional)

---

## 1. Gambaran Umum & Nilai Utama

Pasar listrik grosir modern ditandai oleh volatilitas harga yang sangat ekstrem akibat penetrasi energi terbarukan (fenomena *Duck Curve* dari pembangkit surya), batasan *ramping* generator termal, kejadian harga negatif saat kelebihan pasokan di siang hari, dan lonjakan harga (*price spike*) saat beban puncak petang. Sistem Penyimpanan Energi Baterai (BESS) menangkap peluang penyebaran harga ini melalui arbitrase temporal.

Namun, strategi arbitrase naif sering kali gagal di dunia nyata karena:
- **Rugi Daya Bolak-Balik (Round-Trip Losses)**: Mengabaikan efisiensi konversi termal saat pengisian dan pelepasan mengikis margin arbitrase tipis.
- **Biaya Degradasi Baterai & Umur Siklus**: Siklus pengisian yang tidak terkendali mempercepat degradasi sel dan memicu biaya penggantian baterai yang mahal.
- **Lookahead Bias & Data Snooping**: Model Machine Learning yang dilatih tanpa pemisahan temporal yang ketat menghasilkan profitabilitas palsu.
- **Pelanggaran Batas Fisik Inverter & SoC**: Perintah dispatch yang melanggar batas MW inverter atau cadangan State of Charge (SoC) akan memicu trip proteksi perangkat keras.

**AI Algorithmic Trading & BESS Arbitrage Optimizer** mengatasi tantangan tersebut secara menyeluruh melalui:
- **Rust Control Plane**: Engine performa tinggi untuk validasi risiko *pre-trade* tingkat mikrodetik, *backtester* pemutaran ulang deterministik, dan penegakan *digital twin* fisika baterai.
- **Python ML Microservice**: Layanan terisolasi dengan XGBoost (*walk-forward chronological validation*) dan PyTorch PPO (*Proximal Policy Optimization*) dengan proyeksi aksi terikat analitik (*constrained action mapping*).
- **React 19 + TypeScript + Tailwind CSS v4 Terminal**: Antarmuka institusional untuk memantau jadwal *dispatch*, eksekusi *paper trading*, status kesehatan baterai (SOH), dan analisis performa strategi.

---

## 2. Arsitektur Sistem

```mermaid
flowchart TD
    subgraph Frontend ["Terminal Frontend (Port 3230)"]
        UI["React 19 + TypeScript + Tailwind CSS v4"]
        Views["Ringkasan • Pasar & Prediksi • Digital Twin • Lab PPO • Perencana Dispatch • Backtest • Meja Order • Tata Kelola Data"]
    end

    subgraph Rust ["Rust Control Plane (Port 8230)"]
        AxumServer["Axum HTTP API + Tokio Runtime"]
        TwinEngine["BESS Digital Twin (Fisika & Rugi Daya)"]
        BacktestEngine["Deterministic Replay Backtester (Tanpa Lookahead)"]
        RiskManager["Manajemen Risiko Pre-Trade & Tombol Darurat"]
        PaperAdapter["Adapter Paper Trading (Latensi & Slippage Realistis)"]
        LiveAdapter["Adapter Pasar Riil (Terkunci Aman)"]
        DB[(Penyimpanan SQLite WAL & Jejak Audit)]
    end

    subgraph Python ["Python ML Microservice (Port 8231)"]
        FastAPIApp["FastAPI REST Service"]
        XGBoostModel["XGBoost Price Forecaster + Interval Ketidakpastian"]
        PPOModel["PyTorch PPO Agent (Aksi Terikat Fisik)"]
    end

    subgraph BenchmarkData ["Lapisan Data & Tata Kelola"]
        CAISOData["Benchmark CAISO SP-15 2024 (8.784 Jam Diverifikasi)"]
        CSVImporter["Pengimpor CSV Kustom (Validasi Skema)"]
    end

    UI -->|HTTP Proxy /api| AxumServer
    AxumServer --> TwinEngine
    AxumServer --> BacktestEngine
    AxumServer --> RiskManager
    AxumServer --> PaperAdapter
    AxumServer --> DB
    AxumServer -->|Internal JSON RPC| FastAPIApp
    FastAPIApp --> XGBoostModel
    FastAPIApp --> PPOModel
    CAISOData --> AxumServer
    CSVImporter --> AxumServer
```

### Alokasi Port Layanan
| Layanan | Port | Protokol | Deskripsi |
|---|---|---|---|
| **Terminal Frontend** | `3230` | HTTP / Vite Dev | Antarmuka pengguna terminal trading institusional |
| **Rust Control Plane API** | `8230` | HTTP / REST | Control plane, pemeriksaan risiko, simulasi backtest |
| **Python ML Engine** | `8231` | HTTP / REST | Peramalan harga XGBoost & agen Reinforcement Learning PPO |

---

## 3. Pemodelan Fisika BESS & Ketelitian Matematis

### A. Efisiensi Round-Trip Non-Linear & Konservasi Energi
Digital twin memodelkan efisiensi konversi asimetris saat pengisian (*charging*) dan pelepasan (*discharging*):
$$\eta_{\text{rt}} = \eta_{\text{charge}} \times \eta_{\text{discharge}}$$
*(Nilai standar: $0.94 \times 0.94 \approx 88.36\%$)*

- **Fase Pengisian Daya ($P_{\text{req}} < 0$)**: Daya diserap dari grid $P_{\text{grid}} = |P_{\text{req}}|$. Energi internal yang berhasil disimpan ke dalam sel baterai:
  $$E_{\text{stored}} = P_{\text{grid}} \times \Delta t \times \eta_{\text{charge}}$$
  $$\Delta \text{SoC} = +\frac{E_{\text{stored}}}{E_{\text{nominal}}}$$
- **Fase Pelepasan Daya ($P_{\text{req}} > 0$)**: Daya dikirim ke grid $P_{\text{grid}} = P_{\text{req}}$. Energi internal baterai yang terkuras:
  $$E_{\text{delivered}} = P_{\text{grid}} \times \Delta t$$
  $$E_{\text{depleted}} = \frac{E_{\text{delivered}}}{\eta_{\text{discharge}}}$$
  $$\Delta \text{SoC} = -\frac{E_{\text{depleted}}}{E_{\text{nominal}}}$$

Konservasi energi ditegakkan secara mutlak: kerugian termal inverter dan sel dipotong pada setiap interval waktu, sehingga tidak ada energi gratis yang dihasilkan.

### B. Amplop Operasi & Batas Fisik Keras (Hard Constraints)
- **Rentang State of Charge (SoC)**: Terikat ketat pada $[\text{SoC}_{\min}, \text{SoC}_{\max}]$ (default $10\% \dots 90\%$) untuk mencegah degradasi kimiawi elektroda dan pembentukan dendrit litium.
- **Peringkat Inverter**: Daya aktif tidak boleh melampaui kapasitas nominal inverter $P_{\text{nom}}$ (default $100\text{ MW}$).
- **Batas Headroom Fisik**:
  $$P_{\text{charge,max}} = \frac{(\text{SoC}_{\max} - \text{SoC}) \times E_{\text{nominal}}}{\eta_{\text{charge}} \times \Delta t}$$
  $$P_{\text{discharge,max}} = \frac{(\text{SoC} - \text{SoC}_{\min}) \times E_{\text{nominal}} \times \eta_{\text{discharge}}}{\Delta t}$$

### C. Pemodelan Degradasi Throughput & Biaya Siklus
Biaya degradasi sel baterai dihitung pada setiap langkah keputusan berdasarkan pemakaian throughput energi:
$$C_{\text{deg}} = \text{Throughput (MWh)} \times \frac{\text{Biaya Penggantian Sel per MWh}}{2 \times \text{Cycle Life Nominal}}$$
Equivalent Full Cycles (EFC) dan State of Health (SOH) dilacak secara kontinu:
$$\text{EFC} = \frac{\text{Throughput Kumulatif (MWh)}}{2 \times E_{\text{nominal}}}$$
$$\text{SOH}(t) = 1.0 - (1.0 - \text{SOH}_{\text{EOL}}) \times \frac{\text{EFC}(t)}{\text{Cycle Life Nominal}}$$

---

## 4. Kecerdasan Buatan & Machine Learning

### A. Peramal Harga XGBoost (XGBoost Price Forecaster)
- **Feature Engineering Kausal Tanpa Kebocoran Informasi (Zero Lookahead)**: Hanya menggunakan lag harga historis ($t-1, t-2, t-24, t-48, t-168$), statistik bergulir ($24\text{ jam}, 168\text{ jam}$) dengan pergeseran waktu 1 langkah (`.shift(1)`), *cyclical sine/cosine calendar encoding* (jam, hari, bulan), dan harga pasar Day-Ahead yang telah dirilis hari sebelumnya.
- **Pemisahan Waktu Chronological Walk-Forward**:
  - Jendela Latih (*Train*): 70% awal dari garis waktu kronologis.
  - Jendela Validasi (*Validation*): 15% berikutnya.
  - Jendela Uji (*Out-of-Sample Test*): 15% akhir.
  *(Pemisahan acak/k-fold dilarang keras untuk mencegah kebocoran informasi masa depan).*
- **Kuantifikasi Ketidakpastian (Uncertainty Quantification)**: Deviasi standar residual empiris $\hat{\sigma}$ menghitung interval prediksi parametrik 80% ($z = 1.282$) dan 95% ($z = 1.960$):
  $$\hat{y} \pm z \times \hat{\sigma}$$
- **Evaluasi Baseline yang Adil**: Dibandingkan langsung dengan model acuan **Persistence Naive** ($\hat{y}_t = y_{t-1}$) dan **Seasonal Naive** ($\hat{y}_t = y_{t-24}$).

### B. Kebijakan Reinforcement Learning PPO (PyTorch)
- **Lingkungan Kompatibel Gymnasium**: Markov Decision Process (MDP) yang memodelkan SoC baterai, harga LMP pasar, perkiraan Day-Ahead, *forecast spread*, waktu kalender, dan status dispatch saat ini.
- **Ruang Aksi Kontinu**: $a_t \in [-1.0, 1.0]$ mewakili rasio daya pengisian atau pelepasan terhadap daya nominal.
- **Proyeksi Aksi Terikat Analitik (Analytic Action Projection)**:
  $$\pi(s) \rightarrow a_{\text{proj}} = \operatorname{proj}(a, \text{SoC}, P_{\text{nom}}, \eta)$$
  Fungsi proyeksi ini memetakan aksi agen secara analitik ke batas fisik baterai yang diizinkan sebelum diteruskan ke simulator. Hal ini menjamin 100% kepatuhan terhadap batas fisik tanpa melanggar batasan inverter maupun kapasitas.
- **Fungsi Reward Komprehensif**:
  $$R_t = \text{Pendapatan Kotor} - \text{Biaya Pengisian} - C_{\text{deg}} - \text{Biaya Jaringan/Transaksi}$$

---

## 5. Terminal Trading Frontend

Antarmuka dibangun dengan **React 19**, **TypeScript**, **Tailwind CSS v4**, **Recharts**, dan **Lucide Icons**, mencakup 8 panel fungsional:

1. **Ringkasan (Overview Dashboard)**: Ticker harga pasar terkini, meteran gauge SoC baterai, meteran SOH, jadwal dispatch 24 jam, dan metrik PnL arbitrase.
2. **Pasar & Prediksi (Market & Forecast)**: Grafik riwayat LMP dan perkiraan XGBoost dengan pita keyakinan 80%/95%, metrik kesalahan evaluasi (MAE, RMSE, MAPE), dan pengimpor file CSV.
3. **Digital Twin Baterai (Battery Digital Twin)**: Pengatur parameter perangkat keras interaktif (Kapasitas MWh, Daya Inverter MW, Efisiensi, Biaya Penggantian) dilengkapi simulator eksekusi daya satu langkah.
4. **Lab Strategi PPO (Strategy Lab)**: Kurva pelatihan actor-critic, diagnostik proyeksi aksi, dan papan peringkat perbandingan performa antar strategi.
5. **Perencana Dispatch (Dispatch Planner)**: Tabel rencana 24 jam ke depan berisi harga, daya MW yang direkomendasikan, proyeksi SoC, estimasi margin, dan penjelasan rasional algoritma.
6. **Backtesting & Risiko (Backtesting & Risk)**: Pemutaran ulang deterministik multi-bulan, kurva ekuitas interaktif, visualisasi drawdown, dan kurva analisis sensitivitas parameter (Efisiensi, Biaya Degradasi, Daya MW).
7. **Bidding & Meja Order (Orders Desk)**: Terminal eksekusi paper trading, pratinjau pemeriksaan risiko pra-perdagangan, riwayat order, dan indikator penguncian pasar riil.
8. **Tata Kelola Data & Pengaturan (Data Governance)**: Pelacakan asal-usul dataset (*provenance*), status kesehatan database SQLite WAL, dan penampil log audit keamanan.

---

## 6. Tata Kelola Data & Benchmark CAISO 2024

- **Dataset Benchmark CAISO SP-15 2024**: Berisi 8.784 interval jam penuh (1 Januari s.d. 31 Desember 2024 tahun kabisat) yang mencakup Locational Marginal Pricing (LMP) riil, harga Day-Ahead, beban sistem (MW), pembangkitan surya (MW), pembangkitan angin (MW), dan temperatur (°C).
- **Dinamika Pasar yang Terkandung**:
  - Harga negatif hingga mencapai **-$54.38/MWh** saat pemangkasan pembangkit surya siang hari (*curtailment*).
  - Lonjakan harga petang hari (*evening ramp*) hingga mencapai **$397.66/MWh**.
  - Harga rata-rata pasar: **$39.88/MWh** dengan deviasi standar **$28.94/MWh**.
- **Kamus Data (Data Dictionary)**: Spesifikasi satuan, batasan rentang valid, penanganan nilai hilang, dan rekam jejak sumber didokumentasikan di [`data/datasets/data_dictionary.md`](file:///c:/Users/taufi/Documents/Projects/AI%20Algorithmic%20Trading%20&%20BESS%20Arbitrage%20Optimizer/data/datasets/data_dictionary.md).

---

## 7. Spesifikasi API

Rust Control Plane menyediakan antarmuka REST API pada port `8230`:

| Endpoint | Metode | Deskripsi |
|---|---|---|
| `/api/health` | `GET` | Pemeriksaan kesehatan dan status ketersediaan subsistem |
| `/api/market/latest` | `GET` | Data harga pasar, beban, surya, dan angin terbaru |
| `/api/market/history?limit=100` | `GET` | Rangkaian data interval historis untuk visualisasi grafik |
| `/api/bess/state` | `GET` | Status digital twin baterai saat ini (SoC, SOH, throughput, kapasitas) |
| `/api/bess/config` | `POST` | Memperbarui parameter fisik dan finansial BESS |
| `/api/bess/step` | `POST` | Menjalankan satu langkah simulasi daya diskrit |
| `/api/forecast/predict` | `POST` | Menjalankan inferensi XGBoost lengkap dengan pita keyakinan |
| `/api/strategy/backtest` | `POST` | Menjalankan backtest deterministik membandingkan strategi vs baseline adil |
| `/api/strategy/sensitivity` | `GET` | Menjalankan analisis sensitivitas multi-parameter |
| `/api/dispatch/plan` | `GET` | Membuat jadwal rekomendasi dispatch 24 jam ke depan |
| `/api/orders/execute` | `POST` | Mengirimkan order melalui Risk Manager ke Paper Trading Adapter |
| `/api/orders/history` | `GET` | Mengambil riwayat eksekusi order paper trading |
| `/api/orders/killswitch` | `POST` | Mengaktifkan/menonaktifkan tombol darurat (Emergency Kill-Switch) |
| `/api/audit/logs` | `GET` | Mengambil jejak log audit keamanan dan pemeriksaan risiko dari SQLite |

---

## 8. Panduan Instalasi & Menjalankan Aplikasi

### Prasyarat Sistem
- **Rust & Cargo** (versi 1.75 atau lebih baru)
- **Node.js** (versi 18 atau lebih baru) & **npm**
- **Python** (versi 3.10 atau lebih baru) dengan pustaka `uvicorn`, `fastapi`, `xgboost`, `torch`

### Di Windows (Satu Kali Klik)
Untuk meluncurkan seluruh layanan secara otomatis (Python ML, Rust API, dan Frontend UI):
```cmd
start.bat
```
Untuk memeriksa status layanan dan keterikatan port:
```cmd
status.bat
```
Untuk menghentikan seluruh layanan latar belakang secara bersih:
```cmd
stop.bat
```

### Di Linux / macOS / WSL2
```bash
chmod +x scripts/*.sh
./scripts/start.sh    # Menjalankan layanan di latar belakang
./scripts/status.sh   # Memeriksa status port 3230, 8230, 8231
./scripts/stop.sh     # Menghentikan layanan secara bersih
```

### Mengakses Aplikasi
- **Terminal Trading Frontend**: [http://localhost:3230](http://localhost:3230)
- **Health Check Rust Control Plane**: [http://localhost:8230/api/health](http://localhost:8230/api/health)
- **Health Check Python ML Service**: [http://localhost:8231/health](http://localhost:8231/health)

---

## 9. Verifikasi Pengujian & Quality Gates

Seluruh suite pengujian otomatis dapat dijalankan secara lokal:

### A. Pengujian Backend Rust & Linter Ketat
```bash
cd backend
cargo clippy --all-targets -- -D warnings
cargo test
```
*Pengujian yang Berhasil:*
- `test_round_trip_efficiency_and_losses`: Memverifikasi konversi efisiensi bolak-balik non-linear 88.36% dan pemotongan rugi termal.
- `test_hard_soc_bounds_enforcement`: Memastikan SoC baterai tidak pernah melanggar batas $[\text{SoC}_{\min}, \text{SoC}_{\max}]$.
- `test_inverter_power_rating_limit`: Memverifikasi penolakan oleh Risk Manager saat permintaan MW melebihi batas inverter.
- `test_kill_switch_blocks_orders`: Memverifikasi penghentian order secara atomik seketika saat tombol darurat aktif.
- `test_backtest_determinism_and_baselines`: Memastikan pemutaran ulang backtest 100% deterministik dan perhitungan baseline adil.

### B. Pengujian Python ML Service
```bash
cd ml_service
python -m pytest tests -v
```
*Pengujian yang Berhasil:*
- `test_feature_engineering_no_future_leakage`: Membuktikan nol kebocoran informasi masa depan (*zero lookahead*) pada lag fitur.
- `test_bess_env_physics_and_constraints`: Memastikan lingkungan Gymnasium mematuhi hukum fisika baterai dan efisiensi konversi.
- `test_ppo_agent_action_bounds`: Memverifikasi bahwa aksi kontinu jaringan Actor-Critic dibatasi secara ketat dalam $[-1.0, 1.0]$.

### C. Build Produksi Frontend
```bash
cd frontend
npm run build
```
*Kompilasi TypeScript dan pembuatan bundle Vite sukses dengan 0 kesalahan.*

---

## 10. Manajemen Risiko & Keamanan Operasional

1. **Pre-Trade Risk Manager**: Berada di jalur eksekusi sebelum order diteruskan, memvalidasi kapasitas batas daya inverter, margin keamanan SoC, dan laju kenaikan daya (*ramp rate*).
2. **Emergency Kill-Switch**: Tombol henti darurat atomik di memori Rust Control Plane yang langsung memblokir seluruh pengiriman order dispatch baru jika diaktifkan.
3. **Hard-Locked Live Market Adapter**: Adapter pasar riil (`LiveMarketAdapter`) secara sengaja dikunci dalam kode sumber ([`backend/src/core/market_adapter.rs`](backend/src/core/market_adapter.rs)). Eksekusi pasar riil akan ditolak dengan error eksplisit kecuali `LIVE_MARKET_ENABLED=true` dan kredensial resmi Scheduling Coordinator telah tervalidasi.
4. **Idempotensi & Pencegahan Duplikasi**: Perintah dispatch didebounce berdasarkan stempel waktu interval penyelesaian untuk mencegah eksekusi ganda (*double-dispatch*).
5. **Jejak Audit Kekal (Immutable Audit Trail)**: Setiap pengiriman order, perubahan parameter konfigurasi, penolakan risiko, dan pergantian status tombol darurat dicatat secara permanen di database SQLite WAL.

---

## Lisensi

Proyek ini dilisensikan di bawah Lisensi MIT - lihat file [LICENSE](LICENSE) untuk informasi lebih lanjut.
