"""
Combined portfolio: blend crypto and traditional portfolios.

Loads optimized weights from both crypto and traditional portfolios,
then combines them with a configurable allocation split (e.g., 60% crypto / 40% trad).

Output: data/output/weights_combined.json
"""

import logging
from typing import Any

from src.storage import Storage, get_storage
from src.storage.base import StorageError

logger = logging.getLogger(__name__)


class CombineError(Exception):
    """Error during portfolio combination."""

    def __init__(self, message: str, *, operation: str = "combine") -> None:
        self.message = message
        self.operation = operation
        super().__init__(message)


def combine_portfolios(
    crypto_weight: float = 0.6,
    storage: Storage | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """
    Combine crypto and traditional portfolios into one blended allocation.

    Each sub-portfolio's internal weights are scaled by the allocation fraction.
    For example, if crypto_weight=0.6 and BTC has 50% weight within crypto,
    BTC gets 0.6 * 0.50 = 0.30 in the combined portfolio.

    Args:
        crypto_weight: Fraction allocated to crypto (0-1). Trad gets 1 - crypto_weight.
        storage: Storage instance. If None, resolves from config.
        save: Whether to save results to storage.

    Returns:
        Dictionary with combined weights, per-portfolio metrics, and allocation split.

    Raises:
        CombineError: If either portfolio is missing or weights are invalid.
    """
    if not 0.0 <= crypto_weight <= 1.0:
        raise CombineError(
            f"crypto_weight must be between 0 and 1, got {crypto_weight}",
            operation="validate",
        )

    trad_weight = 1.0 - crypto_weight

    if storage is None:
        storage = get_storage()

    # Load both portfolios
    try:
        crypto = storage.load_output("weights")
    except (StorageError, FileNotFoundError) as e:
        raise CombineError("Crypto portfolio not found", operation="load_crypto") from e

    try:
        trad = storage.load_output("weights_trad")
    except (StorageError, FileNotFoundError) as e:
        raise CombineError(
            "Traditional portfolio not found", operation="load_trad"
        ) from e

    crypto_weights = crypto.get("weights", {})
    trad_weights = trad.get("weights", {})

    if not crypto_weights:
        raise CombineError("Crypto portfolio has no weights", operation="validate")
    if not trad_weights:
        raise CombineError("Traditional portfolio has no weights", operation="validate")

    # Scale and merge
    combined: dict[str, float] = {}
    for symbol, w in crypto_weights.items():
        combined[symbol] = round(float(w) * crypto_weight, 6)
    for symbol, w in trad_weights.items():
        combined[symbol] = round(float(w) * trad_weight, 6)

    # Weighted metrics
    crypto_ret = crypto.get("expected_return", 0.0)
    crypto_vol = crypto.get("volatility", 0.0)
    trad_ret = trad.get("expected_return", 0.0)
    trad_vol = trad.get("volatility", 0.0)

    blended_return = crypto_weight * crypto_ret + trad_weight * trad_ret
    # Simplified volatility (assumes zero cross-correlation between asset classes)
    blended_vol = (
        (crypto_weight**2 * crypto_vol**2 + trad_weight**2 * trad_vol**2) ** 0.5
    )

    result: dict[str, Any] = {
        "weights": combined,
        "allocation": {
            "crypto": crypto_weight,
            "traditional": trad_weight,
        },
        "expected_return": round(blended_return, 6),
        "volatility": round(blended_vol, 6),
        "sharpe_ratio": (
            round(blended_return / blended_vol, 4) if blended_vol > 0 else 0.0
        ),
        "crypto_symbols": list(crypto_weights.keys()),
        "trad_symbols": list(trad_weights.keys()),
        "crypto_metrics": {
            "expected_return": crypto_ret,
            "volatility": crypto_vol,
            "sharpe_ratio": crypto.get("sharpe_ratio"),
        },
        "trad_metrics": {
            "expected_return": trad_ret,
            "volatility": trad_vol,
            "sharpe_ratio": trad.get("sharpe_ratio"),
        },
    }

    if save:
        storage.save_output(result, "weights_combined")
        logger.info(
            "Combined portfolio saved: %.0f%% crypto / %.0f%% trad, %d assets",
            crypto_weight * 100,
            trad_weight * 100,
            len(combined),
        )

    return result
