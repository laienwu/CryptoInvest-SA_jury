"""Tests for the constrained portfolio optimizer module."""

import pytest

from src.pipeline.constrained import (
    ConstrainedError,
    analyze_constrained,
    optimize_constrained,
)


# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

def _test_data():
    """3-asset test data with known covariance and returns."""
    symbols = ["A", "B", "C"]
    mean_returns = [0.10, 0.15, 0.08]
    cov_matrix = [
        [0.04, 0.006, 0.002],
        [0.006, 0.09, 0.004],
        [0.002, 0.004, 0.01],
    ]
    return symbols, mean_returns, cov_matrix


# ---------------------------------------------------------------------------
# optimize_constrained
# ---------------------------------------------------------------------------

class TestOptimizeConstrained:
    def test_no_constraints(self):
        symbols, returns, cov = _test_data()
        result = optimize_constrained(returns, cov, symbols)
        assert "weights" in result
        assert result["sharpe_ratio"] > 0
        total = sum(result["weights"].values())
        assert total == pytest.approx(1.0, abs=0.01)

    def test_min_weight(self):
        symbols, returns, cov = _test_data()
        result = optimize_constrained(
            returns, cov, symbols,
            min_weights={"A": 0.2, "B": 0.2, "C": 0.2},
        )
        for s in ["A", "B", "C"]:
            assert result["weights"].get(s, 0) >= 0.19  # allow small tolerance

    def test_max_weight(self):
        symbols, returns, cov = _test_data()
        result = optimize_constrained(
            returns, cov, symbols,
            max_weights={"A": 0.4, "B": 0.4, "C": 0.4},
        )
        for s in symbols:
            assert result["weights"].get(s, 0) <= 0.41

    def test_min_and_max(self):
        symbols, returns, cov = _test_data()
        result = optimize_constrained(
            returns, cov, symbols,
            min_weights={"A": 0.1},
            max_weights={"B": 0.5},
        )
        assert result["weights"].get("A", 0) >= 0.09
        assert result["weights"].get("B", 0) <= 0.51

    def test_infeasible_min_raises(self):
        symbols, returns, cov = _test_data()
        with pytest.raises(ConstrainedError, match="Infeasible"):
            optimize_constrained(
                returns, cov, symbols,
                min_weights={"A": 0.5, "B": 0.4, "C": 0.3},  # sum=1.2 > 1
            )

    def test_infeasible_max_raises(self):
        symbols, returns, cov = _test_data()
        with pytest.raises(ConstrainedError, match="Infeasible"):
            optimize_constrained(
                returns, cov, symbols,
                max_weights={"A": 0.2, "B": 0.2, "C": 0.2},  # sum=0.6 < 1
            )

    def test_too_few_assets_raises(self):
        with pytest.raises(ConstrainedError, match="at least 2"):
            optimize_constrained([0.1], [[0.04]], ["A"])

    def test_symbols_mismatch_raises(self):
        symbols, returns, cov = _test_data()
        with pytest.raises(ConstrainedError, match="Symbols count"):
            optimize_constrained(returns, cov, ["A", "B"])

    def test_group_constraint(self):
        symbols, returns, cov = _test_data()
        result = optimize_constrained(
            returns, cov, symbols,
            group_constraints=[{"symbols": ["A", "B"], "max_weight": 0.5}],
        )
        ab_weight = result["weights"].get("A", 0) + result["weights"].get("B", 0)
        assert ab_weight <= 0.51  # allow tolerance

    def test_return_keys(self):
        symbols, returns, cov = _test_data()
        result = optimize_constrained(returns, cov, symbols)
        expected = {
            "weights", "expected_return", "volatility", "sharpe_ratio",
            "risk_free_rate", "constraints", "n_assets", "optimization_method",
        }
        assert set(result.keys()) == expected

    def test_constraints_applied_recorded(self):
        symbols, returns, cov = _test_data()
        result = optimize_constrained(
            returns, cov, symbols,
            min_weights={"A": 0.1},
            max_weights={"B": 0.5},
        )
        assert result["constraints"]["min_weights"] == {"A": 0.1}
        assert result["constraints"]["max_weights"] == {"B": 0.5}

    def test_optimization_method(self):
        symbols, returns, cov = _test_data()
        result = optimize_constrained(returns, cov, symbols)
        assert result["optimization_method"] == "constrained_max_sharpe"


# ---------------------------------------------------------------------------
# analyze_constrained (integration)
# ---------------------------------------------------------------------------

class TestAnalyzeConstrained:
    def _make_storage(self, cov_data=None, returns_data=None):
        class MockStorage:
            def __init__(self, processed):
                self._processed = processed
                self._saved = {}

            def load_processed(self, key):
                if key not in self._processed:
                    raise FileNotFoundError(f"Key {key} not found")
                return self._processed[key]

            def save_output(self, data, key):
                self._saved[key] = data

        if cov_data is None:
            cov_data = {
                "symbols": ["A", "B", "C"],
                "matrix": [
                    [0.04, 0.006, 0.002],
                    [0.006, 0.09, 0.004],
                    [0.002, 0.004, 0.01],
                ],
            }
        if returns_data is None:
            returns_data = {"values": [0.10, 0.15, 0.08]}

        return MockStorage({
            "covariance": cov_data,
            "mean_returns": returns_data,
        })

    def test_basic_analysis(self):
        storage = self._make_storage()
        result = analyze_constrained(storage=storage, save=False)
        assert "weights" in result
        assert result["sharpe_ratio"] > 0

    def test_with_constraints(self):
        storage = self._make_storage()
        result = analyze_constrained(
            min_weights={"A": 0.2},
            max_weights={"B": 0.4},
            storage=storage,
            save=False,
        )
        assert result["weights"].get("A", 0) >= 0.19

    def test_missing_data_raises(self):
        class EmptyStorage:
            def load_processed(self, key):
                raise FileNotFoundError("no data")

        with pytest.raises(ConstrainedError, match="Processed data not found"):
            analyze_constrained(storage=EmptyStorage())

    def test_saves_when_requested(self):
        storage = self._make_storage()
        analyze_constrained(storage=storage, save=True)
        assert "weights_constrained" in storage._saved

    def test_no_save_when_disabled(self):
        storage = self._make_storage()
        analyze_constrained(storage=storage, save=False)
        assert "weights_constrained" not in storage._saved


class TestConstrainedError:
    def test_message(self):
        err = ConstrainedError("test")
        assert str(err) == "test"
        assert err.operation == "constrained"

    def test_custom_operation(self):
        err = ConstrainedError("fail", operation="optimize")
        assert err.operation == "optimize"
