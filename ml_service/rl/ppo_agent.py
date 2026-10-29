"""
PyTorch PPO (Proximal Policy Optimization) implementation for BESS Energy Arbitrage.
Implements continuous action Actor-Critic with Generalized Advantage Estimation (GAE)
and clipped surrogate objective.
"""
import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.distributions import Normal
import numpy as np
from typing import Dict, Any, List

class ActorCritic(nn.Module):
    def __init__(self, state_dim: int = 9, action_dim: int = 1):
        super().__init__()
        
        # Shared feature extractor
        self.shared = nn.Sequential(
            nn.Linear(state_dim, 64),
            nn.Tanh(),
            nn.Linear(64, 64),
            nn.Tanh()
        )
        
        # Actor head (mean of continuous action in [-1.0, 1.0])
        self.actor_mean = nn.Sequential(
            nn.Linear(64, action_dim),
            nn.Tanh()
        )
        self.actor_log_std = nn.Parameter(torch.zeros(action_dim))

        # Critic head (state value V(s))
        self.critic = nn.Linear(64, 1)

    def forward(self, state: torch.Tensor):
        feat = self.shared(state)
        mean = self.actor_mean(feat)
        std = self.actor_log_std.exp().expand_as(mean)
        dist = Normal(mean, std)
        val = self.critic(feat)
        return dist, val

class PPOAgent:
    def __init__(
        self,
        state_dim: int = 9,
        action_dim: int = 1,
        lr: float = 3e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_ratio: float = 0.2,
        value_coef: float = 0.5,
        entropy_coef: float = 0.01,
        model_dir: str = "data/models"
    ):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_ratio = clip_ratio
        self.value_coef = value_coef
        self.entropy_coef = entropy_coef
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)

        self.policy = ActorCritic(state_dim, action_dim).to(self.device)
        self.optimizer = optim.Adam(self.policy.parameters(), lr=lr)

    def select_action(self, state, deterministic: bool = False):
        if not isinstance(state, list):
            state = list(state)
        state_t = torch.tensor([state], dtype=torch.float32).to(self.device)
        with torch.no_grad():
            dist, val = self.policy(state_t)
            if deterministic:
                action = dist.mean
            else:
                action = dist.sample()
            log_prob = dist.log_prob(action).sum(dim=-1)
        
        action_val = float(action.detach().cpu().flatten()[0].item())
        clamped_action = max(-1.0, min(1.0, action_val))
        return clamped_action, float(log_prob.item()), float(val.item())

    def train_epoch(self, states, actions, old_log_probs, returns, advantages, epochs=4, batch_size=64):
        # Convert lists directly to torch tensors without intermediate numpy array
        states_list = [list(s) if hasattr(s, '__iter__') else [s] for s in states]
        states_t = torch.tensor(states_list, dtype=torch.float32).to(self.device)
        actions_t = torch.tensor(actions, dtype=torch.float32).unsqueeze(-1).to(self.device)
        old_log_probs_t = torch.tensor(old_log_probs, dtype=torch.float32).unsqueeze(-1).to(self.device)
        returns_t = torch.tensor(returns, dtype=torch.float32).unsqueeze(-1).to(self.device)
        advantages_t = torch.tensor(advantages, dtype=torch.float32).unsqueeze(-1).to(self.device)
        adv_mean = advantages_t.mean()
        adv_std = advantages_t.std()
        advantages_t = (advantages_t - adv_mean) / (adv_std + 1e-8)

        n_samples = len(states)
        epoch_loss = 0.0
        for _ in range(epochs):
            perm = torch.randperm(n_samples)
            for start in range(0, n_samples, batch_size):
                end = min(start + batch_size, n_samples)
                batch_idx = perm[start:end]

                b_states = states_t[batch_idx]
                b_actions = actions_t[batch_idx]
                b_old_log_probs = old_log_probs_t[batch_idx]
                b_returns = returns_t[batch_idx]
                b_adv = advantages_t[batch_idx]

                dist, val = self.policy(b_states)
                new_log_probs = dist.log_prob(b_actions)
                entropy = dist.entropy().mean()

                ratio = torch.exp(new_log_probs - b_old_log_probs)
                surr1 = ratio * b_adv
                surr2 = torch.clamp(ratio, 1.0 - self.clip_ratio, 1.0 + self.clip_ratio) * b_adv
                policy_loss = -torch.min(surr1, surr2).mean()
                val_loss = nn.MSELoss()(val, b_returns)

                total_loss = policy_loss + self.value_coef * val_loss - self.entropy_coef * entropy

                self.optimizer.zero_grad()
                total_loss.backward()
                nn.utils.clip_grad_norm_(self.policy.parameters(), 0.5)
                self.optimizer.step()
                epoch_loss += float(total_loss.item())

        num_batches = max(1, n_samples // batch_size)
        return epoch_loss / (epochs * num_batches)

    def save(self, filename: str = "ppo_bess_model.pt"):
        path = os.path.join(self.model_dir, filename)
        torch.save(self.policy.state_dict(), path)

    def load(self, filename: str = "ppo_bess_model.pt"):
        path = os.path.join(self.model_dir, filename)
        if os.path.exists(path):
            self.policy.load_state_dict(torch.load(path, map_location=self.device))
            self.policy.eval()
            return True
        return False
