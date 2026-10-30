"""
Open Power System Data (OPSD) Multi-Index to BESS Benchmark CSV Converter

This utility extracts single-market time series (Price, Load, Solar, Wind)
from large multi-country OPSD ENTSO-E multiindex datasets (e.g., time_series_60min_multiindex.csv)
and converts them into the exact benchmark schema expected by this platform:
  timestamp,market_id,price_actual,price_day_ahead,system_load_mw,solar_gen_mw,wind_gen_mw,temperature_c,data_quality
"""

import os
import sys
import csv
import argparse
from datetime import datetime

def convert_opsd(input_file: str, output_file: str, country: str = "DE", year: str = "2020"):
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found.")
        sys.exit(1)

    print(f"Reading OPSD Multi-index dataset from: {input_file}")
    print(f"Target Country/Market: {country}, Target Year: {year}")

    with open(input_file, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        try:
            regions = next(reader)
            variables = next(reader)
            attributes = next(reader)
            sources = next(reader)
            webs = next(reader)
            units = next(reader)
            header_col = next(reader)
        except StopIteration:
            print("Error: Empty or malformed CSV.")
            sys.exit(1)

        # Identify Column Indices
        ts_col = 0 # utc_timestamp
        price_col = None
        load_col = None
        solar_col = None
        wind_col = None

        # Search for target country columns
        target_price_regions = [f"{country}_LU", country] if country == "DE" else [country]

        for i, (r, v, a) in enumerate(zip(regions, variables, attributes)):
            r_clean = r.strip()
            v_clean = v.strip().lower()
            a_clean = a.strip().lower()

            if price_col is None and r_clean in target_price_regions and v_clean == "price" and a_clean == "day_ahead":
                price_col = i
            elif load_col is None and r_clean == country and v_clean == "load" and "actual" in a_clean:
                load_col = i
            elif solar_col is None and r_clean == country and v_clean == "solar" and "actual" in a_clean:
                solar_col = i
            elif wind_col is None and r_clean == country and v_clean == "wind" and "actual" in a_clean:
                wind_col = i

        print(f"Detected Columns:")
        print(f" - Timestamp Index: {ts_col}")
        print(f" - Price Index: {price_col} ({regions[price_col] if price_col else 'None'})")
        print(f" - Load Index: {load_col} ({regions[load_col] if load_col else 'None'})")
        print(f" - Solar Index: {solar_col} ({regions[solar_col] if solar_col else 'None'})")
        print(f" - Wind Index: {wind_col} ({regions[wind_col] if wind_col else 'None'})")

        if price_col is None:
            print(f"Error: Could not find Day-Ahead price column for {country}.")
            sys.exit(1)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)

        market_id = f"EPEX_SPOT_{country}"
        exported_count = 0
        prices = []

        with open(output_file, "w", newline="", encoding="utf-8") as out_f:
            writer = csv.writer(out_f)
            # Write Standard Header
            writer.writerow([
                "timestamp",
                "market_id",
                "price_actual",
                "price_day_ahead",
                "system_load_mw",
                "solar_gen_mw",
                "wind_gen_mw",
                "temperature_c",
                "data_quality"
            ])

            for row in reader:
                if not row or len(row) <= max(ts_col, price_col):
                    continue

                ts = row[ts_col].strip()
                if not ts:
                    continue

                # Filter by year if specified
                if year != "all" and not ts.startswith(year):
                    continue

                raw_price = row[price_col].strip()
                if not raw_price:
                    continue # Skip intervals without price

                try:
                    price_da = float(raw_price)
                except ValueError:
                    continue

                # Price actual: Day-Ahead price as benchmark base
                price_act = price_da

                # System Load
                load_val = 0.0
                if load_col and load_col < len(row) and row[load_col].strip():
                    try:
                        load_val = round(float(row[load_col].strip()), 1)
                    except ValueError:
                        load_val = 0.0

                # Solar
                solar_val = 0.0
                if solar_col and solar_col < len(row) and row[solar_col].strip():
                    try:
                        solar_val = round(float(row[solar_col].strip()), 1)
                    except ValueError:
                        solar_val = 0.0

                # Wind
                wind_val = 0.0
                if wind_col and wind_col < len(row) and row[wind_col].strip():
                    try:
                        wind_val = round(float(row[wind_col].strip()), 1)
                    except ValueError:
                        wind_val = 0.0

                # Default European seasonal temperature approximation
                # or nominal 15 C
                temp_c = 15.0

                quality = "VALID"

                writer.writerow([
                    ts,
                    market_id,
                    f"{price_act:.2f}",
                    f"{price_da:.2f}",
                    f"{load_val:.1f}",
                    f"{solar_val:.1f}",
                    f"{wind_val:.1f}",
                    f"{temp_c:.1f}",
                    quality
                ])

                prices.append(price_act)
                exported_count += 1

        if exported_count > 0:
            avg_p = sum(prices) / exported_count
            min_p = min(prices)
            max_p = max(prices)
            neg_p = sum(1 for p in prices if p < 0)
            file_kb = os.path.getsize(output_file) / 1024
            print(f"\n[OK] Successfully converted {exported_count} interval records to {output_file} ({file_kb:.1f} KB)")
            print(f"   Summary: Avg Price: {avg_p:.2f} EUR/MWh | Min: {min_p:.2f} | Max: {max_p:.2f} | Negative Hours: {neg_p}")
        else:
            print("\n[Warning] No records matched the filter criteria.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert OPSD Multi-index CSV to BESS Optimizer Benchmark Dataset")
    parser.add_argument("--input", "-i", required=True, help="Path to raw time_series_60min_multiindex.csv")
    parser.add_argument("--output", "-o", default="data/datasets/opsd_germany_2020.csv", help="Output CSV path")
    parser.add_argument("--country", "-c", default="DE", help="Country code (DE, AT, FR, etc.)")
    parser.add_argument("--year", "-y", default="2020", help="Filter year (e.g. 2020, 2019, or all)")
    args = parser.parse_args()

    convert_opsd(args.input, args.output, args.country, args.year)
