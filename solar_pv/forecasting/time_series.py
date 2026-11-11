"""
Chronological Time-Series Splitting and Walk-Forward Cross-Validation.
Guarantees zero future data snooping or temporal leakage for solar PV forecasting.
"""
from typing import Tuple, Generator, List, Dict, Any
import numpy as np
import pandas as pd


class ChronologicalSplitter:
    """
    Splits time-series data chronologically without random shuffling.
    """

    @staticmethod
    def train_val_test_split(
        df: pd.DataFrame,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        Split DataFrame into strictly chronological Train, Validation, and Test partitions.
        """
        assert abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-5, "Split ratios must sum to 1.0"
        n = len(df)
        train_end = int(n * train_ratio)
        val_end = int(n * (train_ratio + val_ratio))

        train_df = df.iloc[:train_end].copy()
        val_df = df.iloc[train_end:val_end].copy()
        test_df = df.iloc[val_end:].copy()

        return train_df, val_df, test_df

    @staticmethod
    def walk_forward_cv(
        df: pd.DataFrame,
        n_splits: int = 4,
        min_train_steps: int = 168, # 1 week minimum
        test_steps: int = 24         # 24 hours per test fold
    ) -> Generator[Tuple[pd.DataFrame, pd.DataFrame], None, None]:
        """
        Expanding-window (walk-forward) time-series cross validation generator.
        Each fold trains strictly on the past [0 : t] and tests on the immediate next window [t : t + test_steps].
        """
        n = len(df)
        available_steps = n - min_train_steps
        if available_steps < test_steps:
            raise ValueError(f"Not enough data for walk-forward CV: n={n}, min_train={min_train_steps}, test={test_steps}")

        step_increment = max(1, (available_steps - test_steps) // max(1, n_splits - 1))

        for fold in range(n_splits):
            train_end = min_train_steps + fold * step_increment
            test_end = min(n, train_end + test_steps)
            if train_end >= n or (test_end - train_end) < 1:
                break

            train_fold = df.iloc[:train_end]
            test_fold = df.iloc[train_end:test_end]
            yield train_fold, test_fold
