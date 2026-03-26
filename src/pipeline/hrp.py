"""
Hierarchical Risk Parity (HRP) portfolio allocation module.

Implements the HRP algorithm by Marcos Lopez de Prado, which uses
hierarchical clustering on the correlation matrix to build a
diversified portfolio without requiring covariance matrix inversion.

Steps:
1. Convert correlation matrix to distance matrix
2. Single-linkage agglomerative clustering
3. Quasi-diagonalization (seriation) of assets
4. Recursive bisection to allocate weights by inverse variance

Output: data/output/hrp.json
"""

import logging
import math
from typing import Any

from src.pipeline.optimize import (
    calculate_portfolio_return,
    calculate_portfolio_variance,
)
from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class HRPError(Exception):
    """Error during HRP allocation."""

    def __init__(self, message: str, *, operation: str = "hrp") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def _correlation_to_distance(corr_matrix: list[list[float]]) -> list[list[float]]:
    """
    Convert a correlation matrix to a distance matrix.

    Uses the standard transformation: d(i,j) = sqrt(0.5 * (1 - corr(i,j))).
    Perfect correlation (1.0) maps to distance 0, zero correlation to ~0.707,
    and perfect negative correlation (-1.0) to distance 1.0.

    Args:
        corr_matrix: Symmetric correlation matrix [n x n] with values in [-1, 1].

    Returns:
        Distance matrix [n x n] with values in [0, 1].
    """
    n = len(corr_matrix)
    dist: list[list[float]] = []
    for i in range(n):
        row: list[float] = []
        for j in range(n):
            # Clamp to valid range to avoid negative sqrt argument
            clamped = max(-1.0, min(1.0, corr_matrix[i][j]))
            row.append(math.sqrt(0.5 * (1.0 - clamped)))
        dist.append(row)
    return dist


def _single_linkage_cluster(
    dist_matrix: list[list[float]],
) -> list[tuple[int, int, float]]:
    """
    Agglomerative clustering with single linkage.

    At each step, merges the two closest clusters (minimum distance between
    any pair of points across the two clusters).

    Args:
        dist_matrix: Symmetric distance matrix [n x n].

    Returns:
        List of (n-1) merge steps: (cluster_a, cluster_b, distance).
        Cluster IDs >= n refer to merged clusters from previous steps.
    """
    n = len(dist_matrix)
    if n <= 1:
        return []

    # Copy distances so we don't mutate input
    dists = [row[:] for row in dist_matrix]

    # Track which original indices belong to each cluster
    clusters: dict[int, list[int]] = {i: [i] for i in range(n)}
    active = set(range(n))
    linkage: list[tuple[int, int, float]] = []
    next_id = n

    for _ in range(n - 1):
        # Find the minimum distance between active clusters
        min_dist = math.inf
        merge_a, merge_b = -1, -1
        active_list = sorted(active)

        for idx_i in range(len(active_list)):
            for idx_j in range(idx_i + 1, len(active_list)):
                ci = active_list[idx_i]
                cj = active_list[idx_j]
                d = dists[ci][cj]
                if d < min_dist:
                    min_dist = d
                    merge_a, merge_b = ci, cj

        linkage.append((merge_a, merge_b, min_dist))

        # Create new cluster
        new_members = clusters[merge_a] + clusters[merge_b]
        clusters[next_id] = new_members

        # Update distance matrix: expand to accommodate new cluster
        # New cluster distance = min of distances to merged clusters (single linkage)
        new_row = [0.0] * (next_id + 1)
        for c in active:
            if c in (merge_a, merge_b):
                continue
            new_row[c] = min(dists[merge_a][c], dists[merge_b][c])

        # Extend all existing rows with placeholder
        for row in dists:
            row.append(0.0)
        # Add new row
        new_row.append(0.0)
        dists.append(new_row)

        # Mirror distances
        for c in active:
            if c in (merge_a, merge_b):
                continue
            dists[c][next_id] = new_row[c]

        active.discard(merge_a)
        active.discard(merge_b)
        active.add(next_id)
        next_id += 1

    return linkage


def _quasi_diagonalize(
    linkage: list[tuple[int, int, float]], n: int
) -> list[int]:
    """
    Reorder assets so correlated ones are adjacent (seriation).

    Traverses the linkage tree and builds an ordering that places
    similar assets next to each other — the quasi-diagonal structure
    that HRP exploits for recursive bisection.

    Args:
        linkage: Merge steps from single-linkage clustering.
        n: Number of original assets.

    Returns:
        Ordered list of original asset indices.
    """
    if n == 0:
        return []
    if n == 1:
        return [0]

    # Build tree: each merged cluster stores its two children
    children: dict[int, tuple[int, int]] = {}
    for step_idx, (a, b, _dist) in enumerate(linkage):
        cluster_id = n + step_idx
        children[cluster_id] = (a, b)

    # Root is the last merged cluster
    root = n + len(linkage) - 1

    # Iterative DFS to get leaf order
    order: list[int] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node < n:
            # Leaf node = original asset
            order.append(node)
        else:
            left, right = children[node]
            # Push right first so left is processed first
            stack.append(right)
            stack.append(left)

    return order


def _recursive_bisection(
    cov_matrix: list[list[float]], order: list[int]
) -> list[float]:
    """
    Allocate weights via top-down recursive bisection on inverse variance.

    Splits the ordered asset list in half at each level. Each half receives
    a weight proportional to the inverse of its cluster variance. Recurse
    until individual assets are reached.

    Args:
        cov_matrix: Covariance matrix [n x n].
        order: Quasi-diagonalized asset index ordering.

    Returns:
        Weights list of length n, indexed by original asset position.
    """
    n = len(cov_matrix)
    if n == 0:
        return []

    # Initialize all weights to 1.0, then scale by bisection
    weights = {i: 1.0 for i in order}

    # Use a queue of clusters to split
    clusters: list[list[int]] = [order]

    while clusters:
        next_clusters: list[list[int]] = []
        for cluster in clusters:
            if len(cluster) <= 1:
                continue
            mid = len(cluster) // 2
            left = cluster[:mid]
            right = cluster[mid:]

            # Compute inverse-variance weight for each half
            left_var = _cluster_variance(cov_matrix, left)
            right_var = _cluster_variance(cov_matrix, right)

            # Inverse variance allocation
            inv_left = 1.0 / max(left_var, 1e-12)
            inv_right = 1.0 / max(right_var, 1e-12)
            alloc_left = inv_left / (inv_left + inv_right)
            alloc_right = 1.0 - alloc_left

            for i in left:
                weights[i] *= alloc_left
            for i in right:
                weights[i] *= alloc_right

            next_clusters.append(left)
            next_clusters.append(right)

        clusters = next_clusters

    # Convert to list indexed by original position
    result = [0.0] * n
    for i in order:
        result[i] = weights[i]
    return result


def _cluster_variance(cov_matrix: list[list[float]], indices: list[int]) -> float:
    """
    Compute the variance of an equal-weight sub-portfolio over given indices.

    Args:
        cov_matrix: Full covariance matrix.
        indices: Asset indices in this cluster.

    Returns:
        Cluster variance (w' * Cov_sub * w with w = 1/k for k assets).
    """
    k = len(indices)
    if k == 0:
        return 0.0
    w = 1.0 / k
    variance = 0.0
    for i in indices:
        for j in indices:
            variance += w * w * cov_matrix[i][j]
    return variance


def compute_hrp_weights(
    cov_matrix: list[list[float]], corr_matrix: list[list[float]]
) -> dict[str, Any]:
    """
    Full HRP pipeline: distance -> cluster -> quasi-diag -> recursive bisection.

    Args:
        cov_matrix: Annualized covariance matrix [n x n].
        corr_matrix: Correlation matrix [n x n].

    Returns:
        Dictionary with:
            - weights: list of portfolio weights (indexed by asset)
            - order: quasi-diagonalized asset ordering
            - n_assets: number of assets
    """
    n = len(cov_matrix)
    if n == 0:
        return {"weights": [], "order": [], "n_assets": 0}
    if n == 1:
        return {"weights": [1.0], "order": [0], "n_assets": 1}

    dist = _correlation_to_distance(corr_matrix)
    linkage = _single_linkage_cluster(dist)
    order = _quasi_diagonalize(linkage, n)
    weights = _recursive_bisection(cov_matrix, order)

    return {
        "weights": [round(w, 6) for w in weights],
        "order": order,
        "n_assets": n,
    }


def analyze_hrp(
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Run HRP allocation using processed data from storage.

    Loads returns (symbols, annualized_mean), covariance (matrix),
    and correlation (matrix), then runs the full HRP pipeline.

    Args:
        storage: Storage instance (uses default if None).
        save: Whether to save results to storage.

    Returns:
        HRP portfolio with named weights, metrics, and ordering.

    Raises:
        HRPError: If processed data is missing or incomplete.
    """
    if storage is None:
        storage = get_storage()

    try:
        returns_data = storage.load_processed("returns")
        cov_data = storage.load_processed("covariance")
        corr_data = storage.load_processed("correlation")
    except (StorageError, FileNotFoundError) as e:
        raise HRPError(
            "Processed data not found (returns/covariance/correlation)",
            operation="load",
        ) from e

    symbols = returns_data.get("symbols", [])
    mean_returns = returns_data.get("annualized_mean", [])
    cov_matrix = cov_data.get("matrix", [])
    corr_matrix = corr_data.get("matrix", [])

    if not symbols or not cov_matrix or not corr_matrix:
        raise HRPError("Processed data is incomplete", operation="validate")

    hrp = compute_hrp_weights(cov_matrix, corr_matrix)
    weights_list = hrp["weights"]

    # Expected return
    if mean_returns and len(mean_returns) == len(symbols):
        exp_return = calculate_portfolio_return(weights_list, mean_returns)
    else:
        exp_return = 0.0

    # Volatility
    port_var = calculate_portfolio_variance(weights_list, cov_matrix)
    port_vol = math.sqrt(max(port_var, 0.0))

    # Sharpe ratio
    sharpe = (exp_return / port_vol) if port_vol > 0 else 0.0

    # Named weights
    weights_dict = {
        symbols[i]: weights_list[i] for i in range(len(symbols))
    }

    result: dict[str, Any] = {
        "weights": weights_dict,
        "expected_return": round(exp_return, 6),
        "volatility": round(port_vol, 6),
        "sharpe_ratio": round(sharpe, 4),
        "order": hrp["order"],
        "n_assets": hrp["n_assets"],
        "method": "hrp",
    }

    if save:
        storage.save_output(result, "hrp")
        logger.info(
            "HRP: %d assets, vol=%.4f, sharpe=%.4f",
            len(symbols),
            port_vol,
            sharpe,
        )

    return result
