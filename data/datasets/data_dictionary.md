# Market Data Dictionary & Governance Specification

## 1. Overview
Platform **AI Algorithmic Trading & BESS Arbitrage Optimizer** menerapkan tata kelola data yang ketat untuk memastikan integritas, reproduksibilitas, dan pencegahan kebocoran data masa depan (*lookahead bias* / *future leakage*).

Setiap data point wajib memiliki:
- **Timestamp ISO 8601** (dengan timezone eksplisit, misal `2024-01-01T00:00:00Z` atau `-08:00`).
- **Data Provenance**: Kategori sumber (`HISTORICAL_OBSERVATION`, `DAY_AHEAD_FORECAST`, `REAL_TIME_ACTUAL`, `SYNTHETIC_SIMULATED`).
- **Status Kualitas**: `VALID`, `INTERPOLATED`, `STALE`, `MISSING`, `OUTLIER_CAPPED`.
- **Satuan Metrik** yang konsisten.

---

## 2. Schema Kolom CSV / Market Feed

| Kolom | Tipe | Satuan | Deskripsi & Batasan |
|---|---|---|---|
| `timestamp` | String (ISO 8601) | UTC atau Local Offset | Waktu awal interval settlement (misal `2024-01-01T00:00:00Z`). |
| `market_id` | String | - | Identifier pasar (`CAISO_SP15`, `ERCOT_HOUSTON`, `NEM_NSW1`, `SYNTHETIC_BENCHMARK`). |
| `price_actual` | Float | $/MWh | Harga kliring aktual (LMP / RTM). Dapat bernilai negatif saat oversupply renewable. |
| `price_day_ahead` | Float | $/MWh | Harga Day-Ahead Market (DAM) yang dirilis 24 jam sebelumnya. |
| `system_load_mw` | Float | MW | Beban sistem tenaga listrik aktual. |
| `solar_gen_mw` | Float | MW | Pembangkitan tenaga surya aktual / prediksi. |
| `wind_gen_mw` | Float | MW | Pembangkitan tenaga bayu aktual / prediksi. |
| `temperature_c` | Float | °C | Suhu lingkungan rata-rata (memengaruhi efisiensi termal BESS & beban pendingin). |
| `data_quality` | Enum String | - | `VALID`, `STALE`, `MISSING`, `SYNTHETIC`. |

---

## 3. Aturan Settlement & Satuan

- **Daya Listrik (Power)**: Dinyatakan dalam MegaWatt (`MW`).
  - Nilai positif ($P > 0$): **Discharging** (Baterai menyuplai daya ke jaringan/grid, menghasilkan pendapatan).
  - Nilai negatif ($P < 0$): **Charging** (Baterai menyerap daya dari jaringan, mengeluarkan biaya energi).
- **Kapasitas Energi**: Dinyatakan dalam MegaWatt-jam (`MWh`).
- **State of Charge (SoC)**: Fraksi tanpa satuan ($0.0 \dots 1.0$) atau persentase ($0\% \dots 100\%$).
- **Settlement Interval ($\Delta t$)**: 1.0 jam (Hourly), 0.5 jam (Half-hourly), atau 0.25 jam (15-minute).
- **Round-Trip Efficiency ($\eta_{rt}$)**: $\eta_{rt} = \eta_{charge} \times \eta_{discharge}$.
- **Throughput & Equivalent Full Cycles (EFC)**:
  $$\text{EFC} = \frac{\sum |P_{dis}| \cdot \Delta t}{E_{nom}}$$

---

## 4. Model Degradasi Baterai

Biaya degradasi tidak boleh diabaikan atau dikarang:
1. **Model Throughput-based**:
   $$C_{deg} = \frac{C_{cell\_rep}}{2 \cdot N_{cycles} \cdot E_{nom}} \cdot |P| \cdot \Delta t$$
   dimana:
   - $C_{cell\_rep}$: Biaya penggantian sel ($/kWh atau $/MWh).
   - $N_{cycles}$: Umur siklus nominal pada 80% DoD (misal 5,000 siklus untuk LFP).
2. **Model Rainflow DoD Stress**:
   Memperhitungkan kedalaman pengosongan (Depth-of-Discharge) non-linear dengan penalti pada SoC ekstrem (<10% atau >90%).

---

## 5. Provenance & Transparansi Data

- **Dataset Sintetis**: Jika pengguna menguji tanpa data historis riil, data diberi label permanen `SYNTHETIC_SIMULATED`. Dashboard dan laporan akan menampilkan banner peringatan oranye bahwa hasil tidak mewakili performa pasar nyata.
- **Data Historis Riil**: Dilengkapi dengan metadata tanggal unduh, API provider/sumber resmi, dan nomor revisi.
