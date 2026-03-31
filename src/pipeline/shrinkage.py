"""
Ledoit-Wolf covariance shrinkage estimator.

Shrinks the sample covariance matrix toward a structured target (constant
correlation model) to reduce estimation error.  The optimal shrinkage
intensity is determined analytically following Ledoit & Wolf (2004).

Benefits over raw sample covariance:
- Better-conditioned matrix (lower condition number)
- Reduced estimation noise in off-diagonal entries
- More stable portfolio optimization

Output: data/output/shrinkage.json
"""

import logging
import math
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class ShrinkageError(Exception):
    """Error during covariance shrinkage estimation."""

    def __init__(self, message: str, *, operation: str = "shrinkage") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


# =============================================================================
# Sample Covariance
# =============================================================================


def _sample_covariance(returns_matrix: list[list[float]]) -> list[list[float]]:
    """
    Compute the sample covariance matrix from per-asset return series.

    Args:
        returns_matrix: returns_matrix[i] is the list of returns for asset i.
                        All inner lists must have the same length.

    Returns:
        NxN covariance matrix (list of lists).

    Raises:
        ShrinkageError: If fewer than 2 observations or inconsistent lengths.
    """
    n_assets = len(returns_matrix)
    if n_assets == 0:
        raise ShrinkageError("No assets provided", operation="sample_covariance")

    n_obs = len(returns_matrix[0])
    if n_obs < 2:
        raise ShrinkageError(
            f"Need at least 2 observations, got {n_obs}",
            operation="sample_covariance",
        )

    for i, series in enumerate(returns_matrix):
        if len(series) != n_obs:
            raise ShrinkageError(
                f"Asset {i} has {len(series)} observations, expected {n_obs}",
                operation="sample_covariance",
            )

    # Compute means
    means = [sum(series) / n_obs for series in returns_matrix]

    # Compute covariance (unbiased: divide by n_obs - 1)
    cov: list[list[float]] = []
    for i in range(n_assets):
        row: list[float] = []
        for j in range(n_assets):
            s = 0.0
            for t in range(n_obs):
                s += (returns_matrix[i][t] - means[i]) * (returns_matrix[j][t] - means[j])
            row.append(s / (n_obs - 1))
        cov.append(row)

    return cov


# =============================================================================
# Constant Correlation Target
# =============================================================================


def _constant_correlation_target(
    sample_cov: list[list[float]],
) -> list[list[float]]:
    """
    Construct the constant-correlation shrinkage target.

    Target F where:
    - F_ii = S_ii  (diagonal preserved)
    - F_ij = sqrt(S_ii * S_jj) * r_avg  for i != j

    r_avg is the average of all pairwise sample correlations.

    Args:
        sample_cov: NxN sample covariance matrix.

    Returns:
        NxN target matrix.
    """
    n = len(sample_cov)
    if n <= 1:
        # Single asset: target = sample
        return [row[:] for row in sample_cov]

    # Compute pairwise correlations and average
    correlations: list[float] = []
    for i in range(n):
        for j in range(i + 1, n):
            var_i = sample_cov[i][i]
            var_j = sample_cov[j][j]
            denom = math.sqrt(var_i * var_j) if var_i > 0 and var_j > 0 else 0.0
            if denom > 0:
                correlations.append(sample_cov[i][j] / denom)

    r_avg = sum(correlations) / len(correlations) if correlations else 0.0

    # Build target
    target: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        for j in range(n):
            if i == j:
                row.append(sample_cov[i][i])
            else:
                row.append(math.sqrt(sample_cov[i][i] * sample_cov[j][j]) * r_avg)
        target.append(row)

    return target


# =============================================================================
# Shrinkage Intensity (Ledoit-Wolf)
# =============================================================================


def compute_shrinkage_intensity(
    returns_matrix: list[list[float]],
    sample_cov: list[list[float]],
    target: list[list[float]],
) -> float:
    """
    Compute the Ledoit-Wolf optimal shrinkage intensity.

    delta = max(0, min(1, kappa / T))

    where kappa = (pi - rho) / gamma:
    - pi:    sum of asymptotic variances of sample covariance entries
    - rho:   sum of asymptotic covariances between sample and target
    - gamma: squared Frobenius distance between target and sample

    Args:
        returns_matrix: returns_matrix[i] is the return series for asset i.
        sample_cov: NxN sample covariance matrix.
        target: NxN shrinkage target matrix.

    Returns:
        Optimal shrinkage intensity in [0, 1].
    """
    n_assets = len(returns_matrix)
    n_obs = len(returns_matrix[0]) if n_assets > 0 else 0

    if n_obs < 2 or n_assets == 0:
        return 1.0  # Maximum shrinkage when data is insufficient

    # Compute means
    means = [sum(series) / n_obs for series in returns_matrix]

    # Demean returns
    demeaned: list[list[float]] = [
        [returns_matrix[i][t] - means[i] for t in range(n_obs)]
        for i in range(n_assets)
    ]

    # pi: sum over (i,j) of Var( x_it * x_jt )
    # For each (i,j), pi_ij = (1/T) * sum_t (x_it*x_jt - s_ij)^2
    pi_sum = 0.0
    for i in range(n_assets):
        for j in range(n_assets):
            s_ij = sample_cov[i][j]
            var_ij = 0.0
            for t in range(n_obs):
                var_ij += (demeaned[i][t] * demeaned[j][t] - s_ij) ** 2
            pi_sum += var_ij / n_obs

    # gamma: squared Frobenius norm of (target - sample)
    gamma = 0.0
    for i in range(n_assets):
        for j in range(n_assets):
            gamma += (target[i][j] - sample_cov[i][j]) ** 2

    if gamma == 0:
        return 0.0  # Target equals sample — no shrinkage needed

    # rho: for constant-correlation target, approximate rho = pi
    # (simplified: asymptotic covariance of target entries equals pi)
    # More precise estimation: use the Ledoit-Wolf formula directly
    # delta_star = pi / (T * gamma)
    delta = pi_sum / (n_obs * gamma)

    return max(0.0, min(1.0, delta))


# =============================================================================
# Full Ledoit-Wolf Pipeline
# =============================================================================


def ledoit_wolf_covariance(
    returns_matrix: list[list[float]],
) -> dict[str, Any]:
    """
    Compute the Ledoit-Wolf shrinkage covariance estimator.

    Full pipeline:
    1. Compute sample covariance S
    2. Compute constant-correlation target F
    3. Compute optimal shrinkage intensity delta
    4. Shrunk estimator = delta * F + (1 - delta) * S

    Args:
        returns_matrix: returns_matrix[i] is the return series for asset i.

    Returns:
        Dict with shrunk_covariance, sample_covariance, target,
        shrinkage_intensity, n_assets, n_observations.
    """
    n_assets = len(returns_matrix)
    n_obs = len(returns_matrix[0]) if n_assets > 0 else 0

    logger.info(
        "Computing Ledoit-Wolf shrinkage: %d assets, %d observations",
        n_assets,
        n_obs,
    )

    sample_cov = _sample_covariance(returns_matrix)
    target = _constant_correlation_target(sample_cov)
    delta = compute_shrinkage_intensity(returns_matrix, sample_cov, target)

    # Shrunk estimator: delta * F + (1 - delta) * S
    shrunk: list[list[float]] = []
    for i in range(n_assets):
        row: list[float] = []
        for j in range(n_assets):
            val = delta * target[i][j] + (1 - delta) * sample_cov[i][j]
            row.append(val)
        shrunk.append(row)

    logger.info("Shrinkage intensity: %.4f", delta)

    return {
        "shrunk_covariance": shrunk,
        "sample_covariance": sample_cov,
        "target": target,
        "shrinkage_intensity": delta,
        "n_assets": n_assets,
        "n_observations": n_obs,
    }


# =============================================================================
# Eigenvalue Comparison
# =============================================================================


def _matrix_multiply(
    a: list[list[float]], b: list[list[float]]
) -> list[list[float]]:
    """Multiply two square matrices."""
    n = len(a)
    result: list[list[float]] = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            s = 0.0
            for k in range(n):
                s += a[i][k] * b[k][j]
            result[i][j] = s
    return result


def _frobenius_off_diag(m: list[list[float]]) -> float:
    """Sum of squared off-diagonal elements."""
    n = len(m)
    total = 0.0
    for i in range(n):
        for j in range(n):
            if i != j:
                total += m[i][j] ** 2
    return total


def _extract_eigenvalues(matrix: list[list[float]], max_iter: int = 100) -> list[float]:
    """
    Extract eigenvalues using Jacobi-like diagonal dominance approach.

    For small matrices, performs iterative Jacobi rotations to diagonalize.
    For practical purposes returns diagonal approximation with Gershgorin bounds.

    Args:
        matrix: NxN symmetric matrix.
        max_iter: Maximum iterations.

    Returns:
        List of eigenvalues (sorted descending).
    """
    n = len(matrix)
    if n == 0:
        return []
    if n == 1:
        return [matrix[0][0]]

    # Work on a copy
    a: list[list[float]] = [row[:] for row in matrix]

    # Jacobi eigenvalue iteration for small matrices
    for _ in range(max_iter):
        # Find largest off-diagonal element
        max_val = 0.0
        p, q = 0, 1
        for i in range(n):
            for j in range(i + 1, n):
                if abs(a[i][j]) > max_val:
                    max_val = abs(a[i][j])
                    p, q = i, j

        # Convergence check
        if max_val < 1e-12:
            break

        # Compute rotation angle
        if abs(a[p][p] - a[q][q]) < 1e-15:
            theta = math.pi / 4
        else:
            theta = 0.5 * math.atan2(2 * a[p][q], a[p][p] - a[q][q])

        c = math.cos(theta)
        s = math.sin(theta)

        # Apply Givens rotation
        new_a: list[list[float]] = [row[:] for row in a]

        for i in range(n):
            if i != p and i != q:
                new_a[i][p] = c * a[i][p] + s * a[i][q]
                new_a[p][i] = new_a[i][p]
                new_a[i][q] = -s * a[i][p] + c * a[i][q]
                new_a[q][i] = new_a[i][q]

        new_a[p][p] = c * c * a[p][p] + 2 * s * c * a[p][q] + s * s * a[q][q]
        new_a[q][q] = s * s * a[p][p] - 2 * s * c * a[p][q] + c * c * a[q][q]
        new_a[p][q] = 0.0
        new_a[q][p] = 0.0

        a = new_a

    eigenvalues = sorted([a[i][i] for i in range(n)], reverse=True)
    return eigenvalues


def compare_eigenvalues(
    sample_cov: list[list[float]],
    shrunk_cov: list[list[float]],
) -> dict[str, Any]:
    """
    Compare eigenvalue spectra of sample and shrunk covariance matrices.

    Lower condition number indicates a better-conditioned matrix,
    which leads to more stable portfolio optimization.

    Args:
        sample_cov: NxN sample covariance matrix.
        shrunk_cov: NxN shrunk covariance matrix.

    Returns:
        Dict with sample/shrunk eigenvalues and condition numbers.
    """
    sample_eigs = _extract_eigenvalues(sample_cov)
    shrunk_eigs = _extract_eigenvalues(shrunk_cov)

    def _condition_number(eigs: list[float]) -> float:
        if not eigs:
            return 0.0
        min_eig = min(abs(e) for e in eigs)
        max_eig = max(abs(e) for e in eigs)
        if min_eig < 1e-15:
            return float("inf")
        return max_eig / min_eig

    return {
        "sample_eigenvalues": sample_eigs,
        "shrunk_eigenvalues": shrunk_eigs,
        "condition_number_sample": _condition_number(sample_eigs),
        "condition_number_shrunk": _condition_number(shrunk_eigs),
    }


# =============================================================================
# Analyze (storage integration)
# =============================================================================


def analyze_shrinkage(
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run Ledoit-Wolf shrinkage analysis on stored returns data.

    Loads processed returns, computes the shrunk covariance estimator,
    compares with the raw sample covariance, and optionally saves results.

    Args:
        storage: Storage backend. Defaults to configured backend.
        save: Whether to save results to storage.

    Returns:
        Dict with shrinkage results and eigenvalue comparison.

    Raises:
        ShrinkageError: If required data is missing from storage.
    """
    if storage is None:
        storage = get_storage()

    # Load returns
    try:
        returns_data = storage.load_processed("returns")
    except (StorageError, FileNotFoundError) as e:
        raise ShrinkageError(
            "Returns data not found in storage", operation="load"
        ) from e

    symbols: list[str] = returns_data.get("symbols", [])
    values: list[list[float]] = returns_data.get("values", [])

    if not symbols or not values:
        raise ShrinkageError("Returns data is empty", operation="validate")

    # Build returns_matrix: per-asset (transpose of values)
    n_assets = len(symbols)
    returns_matrix: list[list[float]] = [
        [values[t][i] for t in range(len(values))]
        for i in range(n_assets)
    ]

    # Compute shrinkage
    lw_result = ledoit_wolf_covariance(returns_matrix)

    # Load raw covariance for comparison
    try:
        raw_cov_data = storage.load_processed("covariance")
        raw_cov_matrix: list[list[float]] = raw_cov_data.get("matrix", [])
    except (StorageError, FileNotFoundError):
        raw_cov_matrix = lw_result["sample_covariance"]
        logger.warning("Raw covariance not found, using sample covariance for comparison")

    # Compare eigenvalues
    eigen_comparison = compare_eigenvalues(raw_cov_matrix, lw_result["shrunk_covariance"])

    result: dict[str, Any] = {
        "symbols": symbols,
        **lw_result,
        "eigenvalue_comparison": eigen_comparison,
    }

    if save:
        storage.save_output(result, "shrinkage")
        logger.info("Shrinkage results saved to storage")

    return result
