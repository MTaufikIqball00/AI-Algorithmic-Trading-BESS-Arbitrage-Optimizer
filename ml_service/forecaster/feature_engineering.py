"""
Feature engineering for electricity price forecasting.
Strictly guarantees ZERO FUTURE LEAKAGE by using only historical lags and shift operations.
"""
import numpy as np
import pandas as pd

FEATURE_COLUMNS = [
    "price_lag_1", "price_lag_2", "price_lag_3", "price_lag_24", "price_lag_48", "price_lag_168",
    "price_roll_mean_24", "price_roll_std_24", "price_roll_min_24", "price_roll_max_24",
    "price_roll_mean_168",
    "price_day_ahead",
    "system_load_mw_lag24", "solar_gen_mw_lag24", "temperature_c",
    "hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend"
]

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate causal, time-safe features for electricity price forecasting.
    Input df must contain: 'timestamp', 'price_actual', 'price_day_ahead'
    Optional: 'system_load_mw', 'solar_gen_mw', 'temperature_c'
    """
    df = df.copy()
    if not np.issubdtype(df['timestamp'].dtype, np.datetime64):
        df['dt'] = pd.to_datetime(df['timestamp'])
    else:
        df['dt'] = df['timestamp']
    
    df = df.sort_values('dt').reset_index(drop=True)
    
    # 1. Price Lags (strictly in the past)
    df['price_lag_1'] = df['price_actual'].shift(1)
    df['price_lag_2'] = df['price_actual'].shift(2)
    df['price_lag_3'] = df['price_actual'].shift(3)
    df['price_lag_24'] = df['price_actual'].shift(24)
    df['price_lag_48'] = df['price_actual'].shift(48)
    df['price_lag_168'] = df['price_actual'].shift(168)
    
    # 2. Rolling Price Statistics (shift(1) ensures current row is excluded)
    df['price_roll_mean_24'] = df['price_actual'].shift(1).rolling(24, min_periods=12).mean()
    df['price_roll_std_24'] = df['price_actual'].shift(1).rolling(24, min_periods=12).std().fillna(0)
    df['price_roll_min_24'] = df['price_actual'].shift(1).rolling(24, min_periods=12).min()
    df['price_roll_max_24'] = df['price_actual'].shift(1).rolling(24, min_periods=12).max()
    df['price_roll_mean_168'] = df['price_actual'].shift(1).rolling(168, min_periods=48).mean()

    # 3. Exogenous Day-Ahead Price (already cleared and published by ISO the day before)
    if 'price_day_ahead' not in df.columns:
        df['price_day_ahead'] = df['price_lag_24']

    # 4. Exogenous Lags (load, solar)
    if 'system_load_mw' in df.columns:
        df['system_load_mw_lag24'] = df['system_load_mw'].shift(24)
    else:
        df['system_load_mw_lag24'] = 25000.0

    if 'solar_gen_mw' in df.columns:
        df['solar_gen_mw_lag24'] = df['solar_gen_mw'].shift(24)
    else:
        df['solar_gen_mw_lag24'] = 0.0

    if 'temperature_c' not in df.columns:
        df['temperature_c'] = 20.0

    # 5. Cyclical Calendar Features
    hours = df['dt'].dt.hour
    dayofweek = df['dt'].dt.dayofweek
    df['hour_sin'] = np.sin(2 * np.pi * hours / 24.0)
    df['hour_cos'] = np.cos(2 * np.pi * hours / 24.0)
    df['dow_sin'] = np.sin(2 * np.pi * dayofweek / 7.0)
    df['dow_cos'] = np.cos(2 * np.pi * dayofweek / 7.0)
    df['is_weekend'] = (dayofweek >= 5).astype(float)

    return df
