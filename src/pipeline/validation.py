"""
Data quality validation for pipeline stages.

Validates data contracts at each pipeline boundary:
- Bronze (raw): OHLCV schema, no nulls, price > 0
- Silver (processed): returns in range, volatility > 0, symmetric matrices
- Gold (output): weights sum to 1, all in [0, 1]

This is a lightweight custom validation framework — no external dependencies.
Each stage has a set of named rules that produce a ValidationResult.
Results are aggregated into a ValidationReport with pass/fail summary.

Example usage:
    >>> from src.pipeline.validation import validate_stage
    >>> report = validate_stage("bronze", raw_data)
    >>> print(report.summary())
    'bronze: 7/7 checks passed'
"""

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Required keys in every OHLCV record
_OHLCV_KEYS = {"timestamp", "open", "high", "low", "close", "volume"}

# Minimum records per symbol (need at least 2 for returns calculation)
_MIN_RECORDS_PER_SYMBOL = 2

# Tolerance for floating-point comparisons
_WEIGHT_SUM_TOLERANCE = 1e-6


# =============================================================================
# Result dataclasses
# =============================================================================


@dataclass
class ValidationResult:
    """Result of a single validation check."""

    rule_name: str
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ValidationReport:
    """Aggregated validation results for a pipeline stage."""

    stage: str
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True only if every rule passed."""
        return all(r.passed for r in self.results)

    @property
    def failed_rules(self) -> list[ValidationResult]:
        """Return only the rules that failed."""
        return [r for r in self.results if not r.passed]

    def summary(self) -> str:
        """Human-readable one-line summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        return f"{self.stage}: {passed}/{total} checks passed"


# =============================================================================
# Custom exception
# =============================================================================


class ValidationError(Exception):
    """Raised when validation is structurally impossible (bad input type)."""

    def __init__(self, message: str, stage: str | None = None):
        self.message = message
        self.stage = stage
        super().__init__(self.message)


# =============================================================================
# Bronze validation (raw OHLCV data)
# =============================================================================


def validate_bronze(
    data: dict[str, list[dict[str, Any]]],
) -> ValidationReport:
    """
    Validate raw OHLCV data at the Bronze stage.

    Rules:
        ohlcv_schema        — all required keys present in each record
        no_null_ohlcv       — no None values in OHLCV fields
        positive_close      — all close prices > 0
        non_negative_volume — all volume >= 0
        high_gte_low        — high >= low for every record
        timestamp_not_empty — timestamp strings are non-empty
        min_records         — at least 2 records per symbol

    Args:
        data: Mapping of symbol -> list of OHLCV dicts.

    Returns:
        ValidationReport with one result per rule.
    """
    report = ValidationReport(stage="bronze")

    # Flatten all records with their symbol for per-record checks
    all_records: list[tuple[str, dict[str, Any]]] = []
    for symbol, records in data.items():
        for record in records:
            all_records.append((symbol, record))

    # Rule: ohlcv_schema — every record has all required keys
    missing: list[dict[str, Any]] = []
    for symbol, record in all_records:
        absent = _OHLCV_KEYS - set(record.keys())
        if absent:
            missing.append({"symbol": symbol, "missing_keys": sorted(absent)})
    report.results.append(
        ValidationResult(
            rule_name="ohlcv_schema",
            passed=len(missing) == 0,
            message="All records have required OHLCV keys"
            if not missing
            else f"{len(missing)} record(s) missing keys",
            details={"violations": missing},
        )
    )

    # Rule: no_null_ohlcv — no None in OHLCV fields
    nulls: list[dict[str, Any]] = []
    for symbol, record in all_records:
        for key in _OHLCV_KEYS:
            if key in record and record[key] is None:
                nulls.append({"symbol": symbol, "field": key})
    report.results.append(
        ValidationResult(
            rule_name="no_null_ohlcv",
            passed=len(nulls) == 0,
            message="No null values in OHLCV fields"
            if not nulls
            else f"{len(nulls)} null value(s) found",
            details={"violations": nulls},
        )
    )

    # Rule: positive_close — close > 0
    bad_close: list[dict[str, Any]] = []
    for symbol, record in all_records:
        close = record.get("close")
        if close is not None and close <= 0:
            bad_close.append({"symbol": symbol, "close": close})
    report.results.append(
        ValidationResult(
            rule_name="positive_close",
            passed=len(bad_close) == 0,
            message="All close prices are positive"
            if not bad_close
            else f"{len(bad_close)} non-positive close price(s)",
            details={"violations": bad_close},
        )
    )

    # Rule: non_negative_volume — volume >= 0
    bad_volume: list[dict[str, Any]] = []
    for symbol, record in all_records:
        volume = record.get("volume")
        if volume is not None and volume < 0:
            bad_volume.append({"symbol": symbol, "volume": volume})
    report.results.append(
        ValidationResult(
            rule_name="non_negative_volume",
            passed=len(bad_volume) == 0,
            message="All volumes are non-negative"
            if not bad_volume
            else f"{len(bad_volume)} negative volume(s)",
            details={"violations": bad_volume},
        )
    )

    # Rule: high_gte_low — high >= low
    bad_hl: list[dict[str, Any]] = []
    for symbol, record in all_records:
        high = record.get("high")
        low = record.get("low")
        if high is not None and low is not None and high < low:
            bad_hl.append({"symbol": symbol, "high": high, "low": low})
    report.results.append(
        ValidationResult(
            rule_name="high_gte_low",
            passed=len(bad_hl) == 0,
            message="High >= Low for all records"
            if not bad_hl
            else f"{len(bad_hl)} record(s) where high < low",
            details={"violations": bad_hl},
        )
    )

    # Rule: timestamp_not_empty — timestamp strings are non-empty
    bad_ts: list[dict[str, Any]] = []
    for symbol, record in all_records:
        ts = record.get("timestamp")
        if ts is not None and (not isinstance(ts, str) or ts.strip() == ""):
            bad_ts.append({"symbol": symbol, "timestamp": ts})
    report.results.append(
        ValidationResult(
            rule_name="timestamp_not_empty",
            passed=len(bad_ts) == 0,
            message="All timestamps are non-empty strings"
            if not bad_ts
            else f"{len(bad_ts)} empty/invalid timestamp(s)",
            details={"violations": bad_ts},
        )
    )

    # Rule: min_records — at least _MIN_RECORDS_PER_SYMBOL per symbol
    short_symbols: list[dict[str, Any]] = []
    for symbol, records in data.items():
        if len(records) < _MIN_RECORDS_PER_SYMBOL:
            short_symbols.append({"symbol": symbol, "count": len(records)})
    report.results.append(
        ValidationResult(
            rule_name="min_records",
            passed=len(short_symbols) == 0,
            message=f"All symbols have >= {_MIN_RECORDS_PER_SYMBOL} records"
            if not short_symbols
            else f"{len(short_symbols)} symbol(s) below minimum",
            details={"violations": short_symbols},
        )
    )

    _log_report(report)
    return report


# =============================================================================
# Silver validation (processed metrics)
# =============================================================================


def validate_silver(
    data: dict[str, Any],
    name: str,
) -> ValidationReport:
    """
    Validate processed data at the Silver stage.

    Dispatches to the appropriate rule set based on metric name:
        returns     — values in [-1, 1]
        volatility  — all values > 0
        correlation — symmetric, diagonal = 1.0, values in [-1, 1]
        covariance  — symmetric

    Args:
        data: The metric dictionary (as produced by transform_data).
        name: Metric name ("returns", "volatility", "correlation", "covariance").

    Returns:
        ValidationReport with rules specific to the metric.
    """
    report = ValidationReport(stage=f"silver/{name}")

    if name == "returns":
        _validate_returns(data, report)
    elif name == "volatility":
        _validate_volatility(data, report)
    elif name == "correlation":
        _validate_correlation(data, report)
    elif name == "covariance":
        _validate_covariance(data, report)
    else:
        report.results.append(
            ValidationResult(
                rule_name="known_metric",
                passed=False,
                message=f"Unknown silver metric: {name}",
            )
        )

    _log_report(report)
    return report


def _validate_returns(data: dict[str, Any], report: ValidationReport) -> None:
    """Returns values must be in [-1, 1] (log returns are bounded)."""
    values = data.get("values", [])
    out_of_range: list[dict[str, Any]] = []
    for i, row in enumerate(values):
        for j, val in enumerate(row):
            if val < -1.0 or val > 1.0:
                out_of_range.append({"symbol_idx": i, "period_idx": j, "value": val})
    report.results.append(
        ValidationResult(
            rule_name="returns_in_range",
            passed=len(out_of_range) == 0,
            message="All returns in [-1, 1]"
            if not out_of_range
            else f"{len(out_of_range)} return(s) outside [-1, 1]",
            details={"violations": out_of_range},
        )
    )


def _validate_volatility(data: dict[str, Any], report: ValidationReport) -> None:
    """Volatility must be > 0 for all symbols."""
    values = data.get("values", [])
    non_positive: list[dict[str, Any]] = []
    for i, val in enumerate(values):
        if val <= 0:
            non_positive.append({"symbol_idx": i, "value": val})
    report.results.append(
        ValidationResult(
            rule_name="volatility_positive",
            passed=len(non_positive) == 0,
            message="All volatilities are positive"
            if not non_positive
            else f"{len(non_positive)} non-positive volatility(ies)",
            details={"violations": non_positive},
        )
    )


def _validate_correlation(data: dict[str, Any], report: ValidationReport) -> None:
    """Correlation matrix: symmetric, diagonal = 1.0, values in [-1, 1]."""
    matrix = data.get("matrix", [])
    n = len(matrix)

    # Rule: symmetric
    asymmetric: list[dict[str, Any]] = []
    for i in range(n):
        for j in range(i + 1, n):
            if abs(matrix[i][j] - matrix[j][i]) > 1e-9:
                asymmetric.append(
                    {"i": i, "j": j, "val_ij": matrix[i][j], "val_ji": matrix[j][i]}
                )
    report.results.append(
        ValidationResult(
            rule_name="correlation_symmetric",
            passed=len(asymmetric) == 0,
            message="Correlation matrix is symmetric"
            if not asymmetric
            else f"{len(asymmetric)} asymmetric pair(s)",
            details={"violations": asymmetric},
        )
    )

    # Rule: diagonal = 1.0
    bad_diag: list[dict[str, Any]] = []
    for i in range(n):
        if abs(matrix[i][i] - 1.0) > 1e-9:
            bad_diag.append({"index": i, "value": matrix[i][i]})
    report.results.append(
        ValidationResult(
            rule_name="correlation_diagonal_one",
            passed=len(bad_diag) == 0,
            message="Correlation diagonal is 1.0"
            if not bad_diag
            else f"{len(bad_diag)} diagonal element(s) != 1.0",
            details={"violations": bad_diag},
        )
    )

    # Rule: values in [-1, 1]
    out_of_range: list[dict[str, Any]] = []
    for i in range(n):
        for j in range(n):
            if matrix[i][j] < -1.0 - 1e-9 or matrix[i][j] > 1.0 + 1e-9:
                out_of_range.append({"i": i, "j": j, "value": matrix[i][j]})
    report.results.append(
        ValidationResult(
            rule_name="correlation_in_range",
            passed=len(out_of_range) == 0,
            message="All correlation values in [-1, 1]"
            if not out_of_range
            else f"{len(out_of_range)} value(s) outside [-1, 1]",
            details={"violations": out_of_range},
        )
    )


def _validate_covariance(data: dict[str, Any], report: ValidationReport) -> None:
    """Covariance matrix must be symmetric."""
    matrix = data.get("matrix", [])
    n = len(matrix)

    asymmetric: list[dict[str, Any]] = []
    for i in range(n):
        for j in range(i + 1, n):
            if abs(matrix[i][j] - matrix[j][i]) > 1e-9:
                asymmetric.append(
                    {"i": i, "j": j, "val_ij": matrix[i][j], "val_ji": matrix[j][i]}
                )
    report.results.append(
        ValidationResult(
            rule_name="covariance_symmetric",
            passed=len(asymmetric) == 0,
            message="Covariance matrix is symmetric"
            if not asymmetric
            else f"{len(asymmetric)} asymmetric pair(s)",
            details={"violations": asymmetric},
        )
    )


# =============================================================================
# Gold validation (optimization output)
# =============================================================================


def validate_gold(data: dict[str, Any]) -> ValidationReport:
    """
    Validate optimization output at the Gold stage.

    Rules:
        weights_sum_to_one  — sum of weights approx 1.0
        weights_non_negative — all weights >= 0
        weights_bounded     — all weights in [0, 1]
        has_expected_return — field exists
        has_volatility      — field exists
        has_sharpe_ratio    — field exists

    Args:
        data: Optimization result dict (as produced by optimize_portfolio).

    Returns:
        ValidationReport with one result per rule.
    """
    report = ValidationReport(stage="gold")

    # Extract weights list (support both dict and list forms)
    weights: list[float] = []
    if "weights_list" in data:
        weights = data["weights_list"]
    elif "weights" in data and isinstance(data["weights"], dict):
        weights = list(data["weights"].values())
    elif "weights" in data and isinstance(data["weights"], list):
        weights = data["weights"]

    # Rule: weights_sum_to_one
    weight_sum = sum(weights) if weights else 0.0
    report.results.append(
        ValidationResult(
            rule_name="weights_sum_to_one",
            passed=abs(weight_sum - 1.0) <= _WEIGHT_SUM_TOLERANCE,
            message=f"Weights sum to {weight_sum:.8f}"
            if abs(weight_sum - 1.0) > _WEIGHT_SUM_TOLERANCE
            else "Weights sum to 1.0",
            details={"sum": weight_sum, "tolerance": _WEIGHT_SUM_TOLERANCE},
        )
    )

    # Rule: weights_non_negative
    negative = [{"index": i, "value": w} for i, w in enumerate(weights) if w < 0]
    report.results.append(
        ValidationResult(
            rule_name="weights_non_negative",
            passed=len(negative) == 0,
            message="All weights are non-negative"
            if not negative
            else f"{len(negative)} negative weight(s)",
            details={"violations": negative},
        )
    )

    # Rule: weights_bounded — all in [0, 1]
    unbounded = [
        {"index": i, "value": w}
        for i, w in enumerate(weights)
        if w < 0 or w > 1.0
    ]
    report.results.append(
        ValidationResult(
            rule_name="weights_bounded",
            passed=len(unbounded) == 0,
            message="All weights in [0, 1]"
            if not unbounded
            else f"{len(unbounded)} weight(s) outside [0, 1]",
            details={"violations": unbounded},
        )
    )

    # Rule: has_expected_return
    report.results.append(
        ValidationResult(
            rule_name="has_expected_return",
            passed="expected_return" in data,
            message="expected_return field present"
            if "expected_return" in data
            else "Missing expected_return field",
        )
    )

    # Rule: has_volatility
    report.results.append(
        ValidationResult(
            rule_name="has_volatility",
            passed="volatility" in data,
            message="volatility field present"
            if "volatility" in data
            else "Missing volatility field",
        )
    )

    # Rule: has_sharpe_ratio
    report.results.append(
        ValidationResult(
            rule_name="has_sharpe_ratio",
            passed="sharpe_ratio" in data,
            message="sharpe_ratio field present"
            if "sharpe_ratio" in data
            else "Missing sharpe_ratio field",
        )
    )

    _log_report(report)
    return report


# =============================================================================
# Stage dispatcher
# =============================================================================


def validate_stage(
    stage: str,
    data: Any,
    name: str | None = None,
) -> ValidationReport:
    """
    Dispatch validation to the appropriate stage handler.

    Args:
        stage: Pipeline stage — "bronze", "silver", or "gold".
        data: The data to validate (type depends on stage).
        name: Metric name, required for silver stage
              ("returns", "volatility", "correlation", "covariance").

    Returns:
        ValidationReport for the requested stage.

    Raises:
        ValueError: If stage is unknown.
    """
    if stage == "bronze":
        return validate_bronze(data)
    elif stage == "silver":
        return validate_silver(data, name or "unknown")
    elif stage == "gold":
        return validate_gold(data)
    else:
        raise ValueError(f"Unknown stage: {stage}")


# =============================================================================
# Internal helpers
# =============================================================================


def _log_report(report: ValidationReport) -> None:
    """Log a validation report at appropriate levels."""
    logger.info(report.summary())
    for result in report.failed_rules:
        logger.warning(
            "FAILED: %s — %s", result.rule_name, result.message
        )
