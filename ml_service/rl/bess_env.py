"""
Gymnasium-compatible Battery Energy Storage System (BESS) Environment.
Features physically grounded state transitions, non-linear round-trip efficiency losses,
cell degradation cost modeling, and hard action constraint projection.
"""
import math
import numpy as np
import pandas as pd
from typing import Tuple, Dict, Any

class BessEnv:
    def __init__(
        self,
        df: pd.DataFrame,
        e_nom_mwh: float = 100.0,
        p_max_mw: float = 50.0,
        soc_min: float = 0.05,
        soc_max: float = 0.95,
        eta_ch: float = 0.94,
        eta_dis: float = 0.94,
        cell_cost_per_mwh: float = 120000.0,
        cycle_life_nominal: float = 5000.0,
        transaction_fee_per_mwh: float = 0.50,
        dt_hours: float = 1.0,
        initial_soc: float = 0.50
    ):
        self.df = df.reset_index(drop=True)
        self.n_steps = len(df)
        self.e_nom = e_nom_mwh
        self.p_max = p_max_mw
        self.soc_min = soc_min
        self.soc_max = soc_max
        self.eta_ch = eta_ch
        self.eta_dis = eta_dis
        self.eta_rt = eta_ch * eta_dis
        self.cell_cost_per_mwh = cell_cost_per_mwh
        self.cycle_life_nominal = cycle_life_nominal
        self.deg_cost_per_mwh_throughput = cell_cost_per_mwh / (2.0 * cycle_life_nominal)
        self.fee_per_mwh = transaction_fee_per_mwh
        self.dt = dt_hours
        self.initial_soc = initial_soc

        self.current_idx = 0
        self.soc = initial_soc
        self.total_revenue = 0.0
        self.total_energy_cost = 0.0
        self.total_degradation_cost = 0.0
        self.total_fee = 0.0
        self.total_throughput_mwh = 0.0
        self.constraint_violations = 0

        # State dimensions: [soc, price, forecast_1, forecast_2, forecast_3, hour_sin, hour_cos, dow_sin, dow_cos]
        self.state_dim = 9
        self.action_dim = 1 # continuous [-1.0, 1.0]

    def reset(self, start_idx: int = 0) -> np.ndarray:
        self.current_idx = start_idx
        self.soc = self.initial_soc
        self.total_revenue = 0.0
        self.total_energy_cost = 0.0
        self.total_degradation_cost = 0.0
        self.total_fee = 0.0
        self.total_throughput_mwh = 0.0
        self.constraint_violations = 0
        return self._get_obs()

    def _get_obs(self) -> np.ndarray:
        row = self.df.iloc[self.current_idx]
        price = float(row['price_actual'])

        # Lags / Forward info for forecast
        p_ahead_1 = float(self.df.iloc[min(self.current_idx + 1, self.n_steps - 1)]['price_day_ahead'])
        p_ahead_2 = float(self.df.iloc[min(self.current_idx + 2, self.n_steps - 1)]['price_day_ahead'])
        p_ahead_3 = float(self.df.iloc[min(self.current_idx + 3, self.n_steps - 1)]['price_day_ahead'])

        hour = row.get('hour', 0) if 'hour' in row else 12
        dow = row.get('dow', 0) if 'dow' in row else 2

        obs = np.array([
            self.soc,
            price / 100.0, # normalized price
            p_ahead_1 / 100.0,
            p_ahead_2 / 100.0,
            p_ahead_3 / 100.0,
            math.sin(2 * math.pi * hour / 24.0),
            math.cos(2 * math.pi * hour / 24.0),
            math.sin(2 * math.pi * dow / 7.0),
            math.cos(2 * math.pi * dow / 7.0)
        ], dtype=np.float32)

        return obs

    def step(self, action: float) -> Tuple[np.ndarray, float, bool, Dict[str, Any]]:
        """
        Action in [-1.0, 1.0]:
        - Negative: Charging request (ratio of P_max)
        - Positive: Discharging request (ratio of P_max)
        - Zero: Idle
        """
        row = self.df.iloc[self.current_idx]
        price = float(row['price_actual'])

        # Hard projection onto physical constraints
        action_mw = float(np.clip(action, -1.0, 1.0)) * self.p_max

        revenue = 0.0
        energy_cost = 0.0
        actual_power = 0.0
        throughput = 0.0

        if action_mw > 0: # Discharging
            # Max power limited by available energy above soc_min
            # SoC_new = SoC - (P_dis * dt) / (E_nom * eta_dis) >= soc_min
            max_dis_power = (self.soc - self.soc_min) * self.e_nom * self.eta_dis / self.dt
            actual_power = max(0.0, min(action_mw, max_dis_power))
            
            energy_dispatched = actual_power * self.dt # MWh delivered to grid
            # Internal cell energy depleted: energy_dispatched / eta_dis
            internal_energy_used = energy_dispatched / self.eta_dis if self.eta_dis > 0 else 0
            self.soc -= internal_energy_used / self.e_nom
            
            revenue = energy_dispatched * price
            throughput = energy_dispatched

        elif action_mw < 0: # Charging
            req_charge_power = abs(action_mw)
            # Max power limited by headroom below soc_max
            # SoC_new = SoC + (P_ch * eta_ch * dt) / E_nom <= soc_max
            max_ch_power = (self.soc_max - self.soc) * self.e_nom / (self.eta_ch * self.dt)
            actual_power = -max(0.0, min(req_charge_power, max_ch_power))

            energy_absorbed = abs(actual_power) * self.dt # MWh drawn from grid
            # Energy stored in cell: energy_absorbed * eta_ch
            energy_stored = energy_absorbed * self.eta_ch
            self.soc += energy_stored / self.e_nom

            energy_cost = energy_absorbed * price
            throughput = energy_absorbed

        # Clamp SoC to numerical precision limits
        self.soc = float(np.clip(self.soc, self.soc_min, self.soc_max))

        # Degradation cost & fees
        deg_cost = throughput * self.deg_cost_per_mwh_throughput
        fee = throughput * self.fee_per_mwh

        step_net_profit = revenue - energy_cost - deg_cost - fee

        self.total_revenue += revenue
        self.total_energy_cost += energy_cost
        self.total_degradation_cost += deg_cost
        self.total_fee += fee
        self.total_throughput_mwh += throughput

        self.current_idx += 1
        done = (self.current_idx >= self.n_steps - 1)

        info = {
            "step": self.current_idx,
            "price": price,
            "action_mw": actual_power,
            "soc": self.soc,
            "revenue": revenue,
            "energy_cost": energy_cost,
            "deg_cost": deg_cost,
            "fee": fee,
            "net_profit": step_net_profit,
            "total_pnl": self.total_revenue - self.total_energy_cost - self.total_degradation_cost - self.total_fee,
            "throughput_mwh": self.total_throughput_mwh,
            "equivalent_full_cycles": self.total_throughput_mwh / (2.0 * self.e_nom)
        }

        # Reward is net arbitrage profit
        reward = step_net_profit / 100.0 # scale for stable RL gradients

        next_obs = self._get_obs() if not done else np.zeros(self.state_dim, dtype=np.float32)
        return next_obs, reward, done, info
