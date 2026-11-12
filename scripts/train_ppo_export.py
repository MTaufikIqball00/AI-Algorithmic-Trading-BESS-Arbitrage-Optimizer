"""
Pre-train and export PyTorch Deep Reinforcement Learning (PPO) weights
for BESS Arbitrage Actor-Critic policy network.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import torch

from ml_service.rl.ppo_agent import PPOAgent
from ml_service.rl.bess_env import BessEnv

def train_and_export():
    dataset_path = os.path.join("data", "datasets", "caiso_hourly_benchmark_2024.csv")
    if not os.path.exists(dataset_path):
        print(f"Dataset not found at {dataset_path}")
        return

    df = pd.read_csv(dataset_path)
    df['dt'] = pd.to_datetime(df['timestamp'])
    df['hour'] = df['dt'].dt.hour
    df['dow'] = df['dt'].dt.dayofweek

    model_dir = os.path.join("data", "models")
    os.makedirs(model_dir, exist_ok=True)

    agent = PPOAgent(state_dim=9, action_dim=1, model_dir=model_dir)
    env = BessEnv(df=df, e_nom_mwh=100.0, p_max_mw=50.0)

    print("Training PyTorch PPO Actor-Critic Neural Network...")
    episodes = 5
    steps_per_episode = 168  # 1 week per episode

    for ep in range(episodes):
        max_start = len(df) - steps_per_episode - 2
        start_idx = np.random.randint(0, max(1, max_start))
        obs = env.reset(start_idx=start_idx)

        states, actions, log_probs, rewards, values, dones = [], [], [], [], [], []
        for t in range(steps_per_episode):
            action, log_prob, val = agent.select_action(obs)
            next_obs, reward, done, info = env.step(action)

            states.append(obs)
            actions.append(action)
            log_probs.append(log_prob)
            rewards.append(reward)
            values.append(val)
            dones.append(done)

            obs = next_obs
            if done:
                break

        # Compute GAE and returns
        returns = []
        advantages = []
        gae = 0.0
        next_val = 0.0
        for step in reversed(range(len(rewards))):
            delta = rewards[step] + agent.gamma * next_val * (1.0 - dones[step]) - values[step]
            gae = delta + agent.gamma * agent.gae_lambda * (1.0 - dones[step]) * gae
            advantages.insert(0, gae)
            returns.insert(0, gae + values[step])
            next_val = values[step]

        loss = agent.train_epoch(states, actions, log_probs, returns, advantages, epochs=2, batch_size=32)
        print(f"Episode {ep + 1}/{episodes} complete - Loss: {loss:.4f} - Throughput: {env.total_throughput_mwh:.1f} MWh")

    agent.save("ppo_bess_model.pt")
    target_path = os.path.join(model_dir, "ppo_bess_model.pt")
    print(f"PyTorch Deep Learning Model successfully exported to: {target_path} ({os.path.getsize(target_path)} bytes)")

if __name__ == "__main__":
    train_and_export()
