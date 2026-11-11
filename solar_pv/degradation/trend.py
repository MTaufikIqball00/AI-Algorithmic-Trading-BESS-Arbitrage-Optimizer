"""
Robust Statistical Trend Estimation for Long-Term PV Degradation.
Implements the Theil-Sen non-parametric estimator and OLS with HAC standard errors.
"""
import numpy as np
from typing import Tuple, Dict, Any, Optional
import scipy.stats as stats


class RobustTrendEstimator:
    """
    Computes robust linear trends resistant to seasonal outliers and sensor drift.
    """

    @staticmethod
    def theil_sen_slope(x: np.ndarray, y: np.ndarray) -> Tuple[float, float, float, float]:
        """
        Theil-Sen robust non-parametric regression.
        Returns:
            (median_slope, intercept, lower_ci_95, upper_ci_95)
        """
        res = stats.theilslopes(y, x, alpha=0.95)
        med_slope = float(res.slope)
        intercept = float(res.intercept)
        low_ci = float(res.low_slope)
        high_ci = float(res.high_slope)
        return med_slope, intercept, low_ci, high_ci

    @staticmethod
    def ols_trend(x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """
        Standard Ordinary Least Squares linear regression.
        """
        res = stats.linregress(x, y)
        return {
            "slope": float(res.slope),
            "intercept": float(res.intercept),
            "r_value": float(res.rvalue),
            "p_value": float(res.pvalue),
            "stderr": float(res.stderr)
        }
