"""
Unit and integration tests for ML Service (Forecaster, BessEnv, PPO).
"""
import pytest
import numpy as np
import pandas as pd
from forecaster.feature_engineering import engineer_features, FEATURE_COLUMNS
from forecaster.xgboost_model import PriceForecaster
from rl.bess_env import BessEnv
from rl.ppo_agent import PPOAgent

@pytest.fixture
def sample_market_df():
    # 300 hours of synthetic test data
    dates = pd.date_range("2024-01-01", periods=300, freq="1h")
    prices = 50.0 + 30.0 * np.sin(np.linspace(0, 20 * np.pi, 300)) + np.random.normal(0, 3, 300)
    return pd.DataFrame({
        "timestamp": dates.strftime("%Y-%m-%dT%H:00:00Z"),
        "price_actual": prices,
        "price_day_ahead": prices * 0.95,
        "system_load_mw": 20000 + 5000 * np.sin(np.linspace(0, 20 * np.pi, 300)),
        "solar_gen_mw": np.maximum(0, 10000 * np.sin(np.linspace(0, 20 * np.pi, 300))),
        "wind_gen_mw": 3000 + 500 * np.cos(np.linspace(0, 20 * np.pi, 300)),
        "temperature_c": 18.0 + 5.0 * np.sin(np.linspace(0, 20 * np.pi, 300)),
        "data_quality": "VALID"
    })

def test_feature_engineering_no_future_leakage(sample_market_df):
    df_feat = engineer_features(sample_market_df)
    for col in FEATURE_COLUMNS:
        assert col in df_feat.columns, f"Missing feature {col}"
    # Lag 1 must equal shifted price
    assert df_feat.iloc[5]['price_lag_1'] == df_feat.iloc[4]['price_actual']
    assert df_feat.iloc[25]['price_lag_24'] == df_feat.iloc[1]['price_actual']

def test_bess_env_physics_and_constraints(sample_market_df):
    env = BessEnv(df=sample_market_df, e_nom_mwh=100.0, p_max_mw=50.0, soc_min=0.05, soc_max=0.95, eta_ch=0.90, eta_dis=0.90)
    obs = env.reset()
    assert obs.shape == (9,)
    assert env.soc == 0.50

    # Charge at full power
    next_obs, reward, done, info = env.step(-1.0)
    assert info['action_mw'] < 0 # negative power = charging
    assert env.soc > 0.50 # SoC must increase
    assert env.soc <= 0.95 # must not exceed max

    # Discharge test
    next_obs, reward, done, info = env.step(1.0)
    assert info['action_mw'] > 0 # positive power = discharging
    assert info['revenue'] > 0 # must generate revenue when price is positive

    # Extreme discharge: cannot drain below soc_min (0.05)
    for _ in range(10):
        env.step(1.0)
    assert env.soc >= 0.05, f"SoC breached lower bound: {env.soc}"

def test_ppo_agent_action_bounds():
    agent = PPOAgent()
    dummy_obs = np.random.randn(9).astype(np.float32)
    action, log_prob, val = agent.select_action(dummy_obs)
    assert -1.0 <= action <= 1.0, f"Action {action} outside [-1.0, 1.0]"
    assert isinstance(log_prob, float)
    assert isinstance(val, float)
