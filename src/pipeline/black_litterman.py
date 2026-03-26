"""
Black-Litterman portfolio optimization module.

Implements the Black-Litterman model which combines market equilibrium
returns with investor views to produce posterior expected returns, then
optimizes the portfolio using those adjusted returns.

The model starts from CAPM equilibrium (implied returns from market-cap
weights), incorporates subjective views via a Bayesian update, and
produces a new set of expected returns that blend prior and views.

Algorithm:
1. Compute equilibrium returns: Pi = delta * Sigma * w
2. Define investor views as P matrix and Q vector
3. Posterior: E[R] = [(tau*Sigma)^-1 + P'*Omega^-1*P]^-1
              * [(tau*Sigma)^-1*Pi + P'*Omega^-1*Q]
4. Optimize portfolio weights using posterior returns

Output: data/output/black_litterman.json
"""

import logging
import math
from typing import Any

from src.pipeline.optimize import (
    calculate_portfolio_return,
    calculate_portfolio_variance,
    dot_product,
    matrix_vector_multiply,
)
from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class BlackLittermanError(Exception):
    """Error during Black-Litterman optimization."""

    def __init__(self, message: str, *, operation: str = "black_litterman") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


# =============================================================================
# Matrix utilities (pure Python, no numpy/pandas)
# =============================================================================


def _matrix_multiply(
    a: list[list[float]], b: list[list[float]]
) -> list[list[float]]:
    """Multiply two matrices A [m x n] * B [n x p] -> [m x p]."""
    m = len(a)
    n = len(b)
    p = len(b[0]) if n > 0 else 0
    result = [[0.0] * p for _ in range(m)]
    for i in range(m):
        for j in range(p):
            result[i][j] = sum(a[i][k] * b[k][j] for k in range(n))
    return result


def _transpose(matrix: list[list[float]]) -> list[list[float]]:
    """Transpose a matrix."""
    if not matrix:
        return []
    rows = len(matrix)
    cols = len(matrix[0])
    return [[matrix[i][j] for i in range(rows)] for j in range(cols)]


def _scale_matrix(
    matrix: list[list[float]], scalar: float
) -> list[list[float]]:
    """Multiply every element of a matrix by a scalar."""
    return [[scalar * matrix[i][j] for j in range(len(matrix[0]))] for i in range(len(matrix))]


def _add_matrices(
    a: list[list[float]], b: list[list[float]]
) -> list[list[float]]:
    """Element-wise addition of two matrices."""
    n = len(a)
    m = len(a[0]) if n > 0 else 0
    return [[a[i][j] + b[i][j] for j in range(m)] for i in range(n)]


def _invert_matrix(matrix: list[list[float]]) -> list[list[float]]:
    """
    Invert a square matrix using Gauss-Jordan elimination.

    Raises:
        BlackLittermanError: If matrix is singular.
    """
    n = len(matrix)
    # Augment with identity
    aug = [row[:] + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(matrix)]

    for col in range(n):
        # Partial pivoting
        max_row = col
        for row in range(col + 1, n):
            if abs(aug[row][col]) > abs(aug[max_row][col]):
                max_row = row
        aug[col], aug[max_row] = aug[max_row], aug[col]

        pivot = aug[col][col]
        if abs(pivot) < 1e-12:
            raise BlackLittermanError(
                "Singular matrix in inversion", operation="invert"
            )

        # Scale pivot row
        for j in range(2 * n):
            aug[col][j] /= pivot

        # Eliminate column
        for row in range(n):
            if row == col:
                continue
            factor = aug[row][col]
            for j in range(2 * n):
                aug[row][j] -= factor * aug[col][j]

    return [row[n:] for row in aug]


def _matrix_vector_product(
    matrix: list[list[float]], vector: list[float]
) -> list[float]:
    """Multiply matrix [m x n] by vector [n] -> [m]."""
    return [sum(matrix[i][j] * vector[j] for j in range(len(vector))) for i in range(len(matrix))]


# =============================================================================
# Black-Litterman model
# =============================================================================


def compute_equilibrium_returns(
    weights: list[float],
    cov_matrix: list[list[float]],
    risk_aversion: float = 2.5,
) -> list[float]:
    """
    Compute implied equilibrium returns (Pi = delta * Sigma * w).

    These are the CAPM-implied expected returns given market-cap weights
    and the covariance structure.

    Args:
        weights: Market-cap or reference weights [n].
        cov_matrix: Annualized covariance matrix [n x n].
        risk_aversion: Risk aversion coefficient (delta). Higher values
            imply lower risk tolerance.

    Returns:
        Equilibrium returns vector [n].
    """
    sigma_w = matrix_vector_multiply(cov_matrix, weights)
    return [risk_aversion * s for s in sigma_w]


def create_view_matrix(
    n_assets: int,
    views: list[dict[str, Any]],
) -> tuple[list[list[float]], list[float]]:
    """
    Build the P (pick) matrix and Q (return) vector from investor views.

    Each view is a dict with:
        - assets: list of asset indices involved in the view
        - weights: corresponding weights (e.g. [1, -1] for relative view)
        - return: expected return of the view

    Args:
        n_assets: Total number of assets in the portfolio.
        views: List of view specifications.

    Returns:
        Tuple of (P matrix [k x n], Q vector [k]) where k = number of views.

    Raises:
        BlackLittermanError: If views are malformed.
    """
    if not views:
        return [], []

    p_matrix: list[list[float]] = []
    q_vector: list[float] = []

    for i, view in enumerate(views):
        assets = view.get("assets", [])
        view_weights = view.get("weights", [])
        view_return = view.get("return", 0.0)

        if len(assets) != len(view_weights):
            raise BlackLittermanError(
                f"View {i}: assets and weights length mismatch",
                operation="create_views",
            )

        row = [0.0] * n_assets
        for idx, w in zip(assets, view_weights):
            if idx < 0 or idx >= n_assets:
                raise BlackLittermanError(
                    f"View {i}: asset index {idx} out of range [0, {n_assets})",
                    operation="create_views",
                )
            row[idx] = w

        p_matrix.append(row)
        q_vector.append(view_return)

    return p_matrix, q_vector


def compute_posterior_returns(
    equilibrium: list[float],
    cov_matrix: list[list[float]],
    p_matrix: list[list[float]],
    q_vector: list[float],
    tau: float = 0.05,
    omega: list[list[float]] | None = None,
) -> list[float]:
    """
    Compute Black-Litterman posterior expected returns.

    E[R] = [(tau*Sigma)^-1 + P' * Omega^-1 * P]^-1
           * [(tau*Sigma)^-1 * Pi + P' * Omega^-1 * Q]

    Args:
        equilibrium: Prior equilibrium returns (Pi) [n].
        cov_matrix: Annualized covariance matrix [n x n].
        p_matrix: Pick matrix [k x n] mapping views to assets.
        q_vector: View return expectations [k].
        tau: Uncertainty scalar on equilibrium (typically 0.01-0.10).
        omega: View uncertainty matrix [k x k]. If None, uses
            proportional omega = tau * P * Sigma * P'.

    Returns:
        Posterior expected returns [n].
    """
    n = len(equilibrium)

    # If no views, return equilibrium unchanged
    if not p_matrix or not q_vector:
        return list(equilibrium)

    # tau * Sigma
    tau_sigma = _scale_matrix(cov_matrix, tau)

    # (tau * Sigma)^-1
    tau_sigma_inv = _invert_matrix(tau_sigma)

    # Compute Omega if not provided: proportional to view uncertainty
    # Omega = tau * P * Sigma * P'  (diagonal approximation)
    if omega is None:
        p_sigma = _matrix_multiply(p_matrix, cov_matrix)
        p_t = _transpose(p_matrix)
        omega_full = _matrix_multiply(p_sigma, p_t)
        omega = _scale_matrix(omega_full, tau)

    # Omega^-1
    omega_inv = _invert_matrix(omega)

    # P' (transpose of P)
    p_t = _transpose(p_matrix)

    # P' * Omega^-1
    pt_omega_inv = _matrix_multiply(p_t, omega_inv)

    # P' * Omega^-1 * P  [n x n]
    pt_omega_inv_p = _matrix_multiply(pt_omega_inv, p_matrix)

    # Left: (tau*Sigma)^-1 + P'*Omega^-1*P  [n x n]
    left = _add_matrices(tau_sigma_inv, pt_omega_inv_p)

    # Invert the left term
    left_inv = _invert_matrix(left)

    # Right term 1: (tau*Sigma)^-1 * Pi  [n]
    right1 = _matrix_vector_product(tau_sigma_inv, equilibrium)

    # Right term 2: P' * Omega^-1 * Q  [n]
    right2 = _matrix_vector_product(pt_omega_inv, q_vector)

    # Combined right: right1 + right2
    right = [right1[i] + right2[i] for i in range(n)]

    # Posterior: left_inv * right
    return _matrix_vector_product(left_inv, right)


def optimize_black_litterman(
    posterior_returns: list[float],
    cov_matrix: list[list[float]],
    risk_free_rate: float = 0.0,
) -> list[float]:
    """
    Find maximum Sharpe ratio portfolio using posterior returns (long-only).

    Uses scipy SLSQP with w >= 0 bounds.

    Args:
        posterior_returns: Black-Litterman posterior expected returns [n].
        cov_matrix: Annualized covariance matrix [n x n].
        risk_free_rate: Risk-free rate for Sharpe calculation.

    Returns:
        Optimal weight vector [n].
    """
    from scipy.optimize import minimize

    n = len(posterior_returns)
    if n == 0:
        return []
    if n == 1:
        return [1.0]

    def neg_sharpe(weights: list[float]) -> float:
        w = list(weights)
        port_return = dot_product(w, posterior_returns)
        var = calculate_portfolio_variance(w, cov_matrix)
        vol = math.sqrt(max(0.0, var)) if var > 0 else 1e-10
        return -(port_return - risk_free_rate) / vol

    constraints = [{"type": "eq", "fun": lambda w: sum(w) - 1.0}]
    bounds = [(0.0, 1.0)] * n

    result = minimize(
        neg_sharpe,
        [1.0 / n] * n,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"ftol": 1e-12, "maxiter": 1000},
    )

    if result.success:
        return [max(0.0, w) for w in result.x]

    logger.warning("Black-Litterman optimization failed, falling back to equal weights")
    return [1.0 / n] * n


def analyze_black_litterman(
    views: list[dict[str, Any]] | None = None,
    risk_aversion: float = 2.5,
    tau: float = 0.05,
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run the full Black-Litterman pipeline using processed data from storage.

    Loads returns and covariance from storage, computes equilibrium returns,
    incorporates investor views, and optimizes the portfolio.

    Args:
        views: Investor views. If None, creates default views.
        risk_aversion: Risk aversion coefficient for equilibrium.
        tau: Uncertainty scalar on prior.
        storage: Storage instance (defaults to get_storage()).
        save: Whether to save results to storage.

    Returns:
        Dictionary with weights, equilibrium/posterior returns, metrics.

    Raises:
        BlackLittermanError: If data is missing or optimization fails.
    """
    if storage is None:
        storage = get_storage()

    try:
        returns_data = storage.load_processed("returns")
        cov_data = storage.load_processed("covariance")
    except (StorageError, FileNotFoundError) as e:
        raise BlackLittermanError(
            "Processed data not found (returns/covariance)", operation="load"
        ) from e

    symbols = returns_data.get("symbols", [])
    mean_returns = returns_data.get("annualized_mean", [])
    cov_matrix = cov_data.get("matrix", [])

    if not symbols or not cov_matrix:
        raise BlackLittermanError(
            "Processed data is incomplete", operation="validate"
        )

    n = len(symbols)

    # Use equal weights as reference if no market-cap data available
    ref_weights = [1.0 / n] * n

    # Step 1: Equilibrium returns
    equilibrium = compute_equilibrium_returns(ref_weights, cov_matrix, risk_aversion)

    # Step 2: Build views
    if views is None:
        # Default views: first asset outperforms by 2%
        views = [
            {"assets": [0], "weights": [1.0], "return": equilibrium[0] + 0.02},
        ]
        if n >= 2:
            # Second view: first asset outperforms second by 1%
            views.append(
                {"assets": [0, 1], "weights": [1.0, -1.0], "return": 0.01},
            )

    p_matrix, q_vector = create_view_matrix(n, views)

    # Step 3: Posterior returns
    posterior = compute_posterior_returns(
        equilibrium, cov_matrix, p_matrix, q_vector, tau=tau
    )

    # Step 4: Optimize
    optimal_weights = optimize_black_litterman(posterior, cov_matrix)

    # Normalize
    total = sum(optimal_weights)
    if total > 0:
        optimal_weights = [w / total for w in optimal_weights]

    # Compute metrics
    exp_return = calculate_portfolio_return(optimal_weights, mean_returns)
    port_var = calculate_portfolio_variance(optimal_weights, cov_matrix)
    port_vol = math.sqrt(max(0.0, port_var))
    sharpe = (exp_return / port_vol) if port_vol > 0 else 0.0

    weights_dict = {
        symbols[i]: round(optimal_weights[i], 6)
        for i in range(n)
        if optimal_weights[i] > 1e-6
    }

    result: dict[str, Any] = {
        "weights": weights_dict,
        "equilibrium_returns": {
            symbols[i]: round(equilibrium[i], 6) for i in range(n)
        },
        "posterior_returns": {
            symbols[i]: round(posterior[i], 6) for i in range(n)
        },
        "views": views,
        "expected_return": round(exp_return, 6),
        "volatility": round(port_vol, 6),
        "sharpe_ratio": round(sharpe, 4),
        "n_assets": len(weights_dict),
        "method": "black_litterman",
        "parameters": {
            "risk_aversion": risk_aversion,
            "tau": tau,
        },
    }

    if save:
        storage.save_output(result, "black_litterman")
        logger.info(
            "Black-Litterman: %d assets, Sharpe=%.4f, tau=%.3f",
            len(weights_dict), sharpe, tau,
        )

    return result
