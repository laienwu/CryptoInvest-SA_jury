"""
Tests for data quality validation framework.

Covers Bronze, Silver, and Gold stage validation rules,
the stage dispatcher, and ValidationReport properties.
"""

import pytest

from src.pipeline.validation import (
    ValidationReport,
    ValidationResult,
    validate_bronze,
    validate_gold,
    validate_silver,
    validate_stage,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def valid_bronze_data() -> dict[str, list[dict]]:
    """Valid OHLCV data for two symbols, 3 records each."""
    return {
        "BTCUSDT": [
            {"timestamp": "2024-01-01", "open": 99.0, "high": 102.0, "low": 98.0, "close": 100.0, "volume": 1000.0},
            {"timestamp": "2024-01-02", "open": 100.0, "high": 105.0, "low": 99.0, "close": 103.0, "volume": 1200.0},
            {"timestamp": "2024-01-03", "open": 103.0, "high": 106.0, "low": 101.0, "close": 105.0, "volume": 1100.0},
        ],
        "ETHUSDT": [
            {"timestamp": "2024-01-01", "open": 49.0, "high": 52.0, "low": 48.0, "close": 50.0, "volume": 500.0},
            {"timestamp": "2024-01-02", "open": 50.0, "high": 53.0, "low": 49.0, "close": 52.0, "volume": 600.0},
            {"timestamp": "2024-01-03", "open": 52.0, "high": 55.0, "low": 51.0, "close": 54.0, "volume": 550.0},
        ],
    }


@pytest.fixture
def valid_returns_data() -> dict:
    """Valid returns data (values in [-1, 1])."""
    return {
        "symbols": ["BTCUSDT", "ETHUSDT"],
        "dates": ["2024-01-02", "2024-01-03"],
        "values": [
            [0.02, -0.01],
            [0.03, 0.01],
        ],
    }


@pytest.fixture
def valid_correlation_data() -> dict:
    """Valid correlation matrix — symmetric, diagonal = 1.0."""
    return {
        "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        "matrix": [
            [1.0, 0.7, 0.5],
            [0.7, 1.0, 0.6],
            [0.5, 0.6, 1.0],
        ],
    }


@pytest.fixture
def valid_gold_data() -> dict:
    """Valid optimization output."""
    return {
        "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
        "weights": {"BTCUSDT": 0.4, "ETHUSDT": 0.35, "BNBUSDT": 0.25},
        "weights_list": [0.4, 0.35, 0.25],
        "expected_return": 0.18,
        "volatility": 0.25,
        "sharpe_ratio": 0.52,
    }


# =============================================================================
# Bronze tests
# =============================================================================


class TestBronzeValidation:
    """Tests for Bronze (raw OHLCV) validation rules."""

    def test_valid_bronze_passes(self, valid_bronze_data):
        """Valid OHLCV data passes all checks."""
        report = validate_bronze(valid_bronze_data)
        assert report.passed
        assert len(report.results) == 7
        assert report.failed_rules == []

    def test_bronze_null_close_fails(self, valid_bronze_data):
        """None in close triggers no_null_ohlcv failure."""
        valid_bronze_data["BTCUSDT"][0]["close"] = None
        report = validate_bronze(valid_bronze_data)
        assert not report.passed
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "no_null_ohlcv" in failed_names

    def test_bronze_negative_close_fails(self, valid_bronze_data):
        """Negative close price fails positive_close."""
        valid_bronze_data["BTCUSDT"][1]["close"] = -1.0
        report = validate_bronze(valid_bronze_data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "positive_close" in failed_names

    def test_bronze_negative_volume_fails(self, valid_bronze_data):
        """Negative volume fails non_negative_volume."""
        valid_bronze_data["ETHUSDT"][0]["volume"] = -1.0
        report = validate_bronze(valid_bronze_data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "non_negative_volume" in failed_names

    def test_bronze_high_lt_low_fails(self, valid_bronze_data):
        """high < low fails high_gte_low."""
        valid_bronze_data["BTCUSDT"][2]["high"] = 90.0
        valid_bronze_data["BTCUSDT"][2]["low"] = 100.0
        report = validate_bronze(valid_bronze_data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "high_gte_low" in failed_names

    def test_bronze_missing_key_fails(self, valid_bronze_data):
        """Missing 'close' key fails ohlcv_schema."""
        del valid_bronze_data["BTCUSDT"][0]["close"]
        report = validate_bronze(valid_bronze_data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "ohlcv_schema" in failed_names

    def test_bronze_empty_timestamp_fails(self, valid_bronze_data):
        """Empty timestamp string fails timestamp_not_empty."""
        valid_bronze_data["ETHUSDT"][1]["timestamp"] = ""
        report = validate_bronze(valid_bronze_data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "timestamp_not_empty" in failed_names

    def test_bronze_whitespace_timestamp_fails(self, valid_bronze_data):
        """Whitespace-only timestamp fails timestamp_not_empty."""
        valid_bronze_data["ETHUSDT"][0]["timestamp"] = "   "
        report = validate_bronze(valid_bronze_data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "timestamp_not_empty" in failed_names

    def test_bronze_single_record_fails(self):
        """Need min 2 records per symbol for returns calculation."""
        data = {
            "BTCUSDT": [
                {"timestamp": "2024-01-01", "open": 99.0, "high": 102.0, "low": 98.0, "close": 100.0, "volume": 1000.0},
            ],
        }
        report = validate_bronze(data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "min_records" in failed_names

    def test_bronze_zero_close_fails(self, valid_bronze_data):
        """Zero close price fails positive_close (close must be > 0)."""
        valid_bronze_data["BTCUSDT"][0]["close"] = 0.0
        report = validate_bronze(valid_bronze_data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "positive_close" in failed_names


# =============================================================================
# Silver tests
# =============================================================================


class TestSilverReturnsValidation:
    """Tests for Silver returns validation."""

    def test_valid_returns_passes(self, valid_returns_data):
        """Valid returns (all in [-1, 1]) pass."""
        report = validate_silver(valid_returns_data, "returns")
        assert report.passed

    def test_returns_out_of_range_fails(self, valid_returns_data):
        """Return > 1 fails returns_in_range."""
        valid_returns_data["values"][0][0] = 1.5
        report = validate_silver(valid_returns_data, "returns")
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "returns_in_range" in failed_names

    def test_returns_below_minus_one_fails(self, valid_returns_data):
        """Return < -1 fails returns_in_range."""
        valid_returns_data["values"][1][1] = -1.2
        report = validate_silver(valid_returns_data, "returns")
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "returns_in_range" in failed_names


class TestSilverVolatilityValidation:
    """Tests for Silver volatility validation."""

    def test_valid_volatility_passes(self):
        """Positive volatilities pass."""
        data = {"symbols": ["BTC", "ETH"], "values": [0.45, 0.55]}
        report = validate_silver(data, "volatility")
        assert report.passed

    def test_zero_volatility_fails(self):
        """Zero volatility fails volatility_positive."""
        data = {"symbols": ["BTC"], "values": [0.0]}
        report = validate_silver(data, "volatility")
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "volatility_positive" in failed_names

    def test_negative_volatility_fails(self):
        """Negative volatility fails volatility_positive."""
        data = {"symbols": ["BTC"], "values": [-0.1]}
        report = validate_silver(data, "volatility")
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "volatility_positive" in failed_names


class TestSilverCorrelationValidation:
    """Tests for Silver correlation matrix validation."""

    def test_valid_correlation_passes(self, valid_correlation_data):
        """Symmetric matrix with diagonal=1 and values in [-1,1] passes."""
        report = validate_silver(valid_correlation_data, "correlation")
        assert report.passed
        assert len(report.results) == 3

    def test_correlation_not_symmetric_fails(self, valid_correlation_data):
        """Asymmetric matrix fails correlation_symmetric."""
        valid_correlation_data["matrix"][0][1] = 0.7
        valid_correlation_data["matrix"][1][0] = 0.3  # break symmetry
        report = validate_silver(valid_correlation_data, "correlation")
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "correlation_symmetric" in failed_names

    def test_correlation_diagonal_not_one_fails(self, valid_correlation_data):
        """Diagonal != 1.0 fails correlation_diagonal_one."""
        valid_correlation_data["matrix"][1][1] = 0.99
        report = validate_silver(valid_correlation_data, "correlation")
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "correlation_diagonal_one" in failed_names

    def test_correlation_out_of_range_fails(self, valid_correlation_data):
        """Value > 1 in correlation matrix fails correlation_in_range."""
        valid_correlation_data["matrix"][0][1] = 1.5
        valid_correlation_data["matrix"][1][0] = 1.5  # keep symmetric
        report = validate_silver(valid_correlation_data, "correlation")
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "correlation_in_range" in failed_names


class TestSilverCovarianceValidation:
    """Tests for Silver covariance matrix validation."""

    def test_valid_covariance_passes(self):
        """Symmetric covariance matrix passes."""
        data = {
            "symbols": ["BTC", "ETH"],
            "matrix": [
                [0.04, 0.02],
                [0.02, 0.09],
            ],
        }
        report = validate_silver(data, "covariance")
        assert report.passed

    def test_covariance_not_symmetric_fails(self):
        """Asymmetric covariance matrix fails."""
        data = {
            "symbols": ["BTC", "ETH"],
            "matrix": [
                [0.04, 0.02],
                [0.05, 0.09],
            ],
        }
        report = validate_silver(data, "covariance")
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "covariance_symmetric" in failed_names


class TestSilverUnknownMetric:
    """Tests for unknown silver metric name."""

    def test_unknown_metric_fails(self):
        """Unknown metric name produces a failure."""
        report = validate_silver({}, "unknown_metric")
        assert not report.passed
        assert report.results[0].rule_name == "known_metric"


# =============================================================================
# Gold tests
# =============================================================================


class TestGoldValidation:
    """Tests for Gold (optimization output) validation rules."""

    def test_valid_gold_passes(self, valid_gold_data):
        """Valid optimization output passes all checks."""
        report = validate_gold(valid_gold_data)
        assert report.passed
        assert len(report.results) == 6

    def test_weights_not_sum_to_one_fails(self, valid_gold_data):
        """Weights that don't sum to 1.0 fail weights_sum_to_one."""
        valid_gold_data["weights_list"] = [0.5, 0.3, 0.1]  # sum = 0.9
        report = validate_gold(valid_gold_data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "weights_sum_to_one" in failed_names

    def test_negative_weight_fails(self, valid_gold_data):
        """Negative weight fails weights_non_negative and weights_bounded."""
        valid_gold_data["weights_list"] = [-0.1, 0.6, 0.5]  # sum = 1.0
        report = validate_gold(valid_gold_data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "weights_non_negative" in failed_names
        assert "weights_bounded" in failed_names

    def test_weight_above_one_fails(self, valid_gold_data):
        """Weight > 1 fails weights_bounded."""
        valid_gold_data["weights_list"] = [1.2, -0.1, -0.1]  # sum = 1.0
        report = validate_gold(valid_gold_data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "weights_bounded" in failed_names

    def test_missing_sharpe_fails(self, valid_gold_data):
        """Missing sharpe_ratio field fails has_sharpe_ratio."""
        del valid_gold_data["sharpe_ratio"]
        report = validate_gold(valid_gold_data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "has_sharpe_ratio" in failed_names

    def test_missing_expected_return_fails(self, valid_gold_data):
        """Missing expected_return field fails has_expected_return."""
        del valid_gold_data["expected_return"]
        report = validate_gold(valid_gold_data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "has_expected_return" in failed_names

    def test_missing_volatility_fails(self, valid_gold_data):
        """Missing volatility field fails has_volatility."""
        del valid_gold_data["volatility"]
        report = validate_gold(valid_gold_data)
        failed_names = [r.rule_name for r in report.failed_rules]
        assert "has_volatility" in failed_names

    def test_gold_weights_from_dict(self):
        """Gold validation works when weights_list is absent (dict only)."""
        data = {
            "weights": {"BTC": 0.6, "ETH": 0.4},
            "expected_return": 0.15,
            "volatility": 0.2,
            "sharpe_ratio": 0.5,
        }
        report = validate_gold(data)
        assert report.passed


# =============================================================================
# Dispatcher & report tests
# =============================================================================


class TestValidateStageDispatcher:
    """Tests for the validate_stage dispatcher."""

    def test_dispatch_bronze(self, valid_bronze_data):
        """Dispatcher routes 'bronze' to validate_bronze."""
        report = validate_stage("bronze", valid_bronze_data)
        assert report.stage == "bronze"
        assert report.passed

    def test_dispatch_silver(self, valid_returns_data):
        """Dispatcher routes 'silver' to validate_silver."""
        report = validate_stage("silver", valid_returns_data, name="returns")
        assert report.stage == "silver/returns"
        assert report.passed

    def test_dispatch_gold(self, valid_gold_data):
        """Dispatcher routes 'gold' to validate_gold."""
        report = validate_stage("gold", valid_gold_data)
        assert report.stage == "gold"
        assert report.passed

    def test_dispatch_unknown_raises(self):
        """Unknown stage raises ValueError."""
        with pytest.raises(ValueError, match="Unknown stage"):
            validate_stage("platinum", {})


class TestValidationReport:
    """Tests for ValidationReport properties."""

    def test_summary_format(self):
        """summary() returns '{stage}: {passed}/{total} checks passed'."""
        report = ValidationReport(stage="test")
        report.results = [
            ValidationResult(rule_name="r1", passed=True, message="ok"),
            ValidationResult(rule_name="r2", passed=False, message="bad"),
            ValidationResult(rule_name="r3", passed=True, message="ok"),
        ]
        assert report.summary() == "test: 2/3 checks passed"

    def test_passed_all_true(self):
        """passed is True when all rules pass."""
        report = ValidationReport(stage="test")
        report.results = [
            ValidationResult(rule_name="r1", passed=True, message="ok"),
            ValidationResult(rule_name="r2", passed=True, message="ok"),
        ]
        assert report.passed is True

    def test_passed_one_false(self):
        """passed is False when any rule fails."""
        report = ValidationReport(stage="test")
        report.results = [
            ValidationResult(rule_name="r1", passed=True, message="ok"),
            ValidationResult(rule_name="r2", passed=False, message="bad"),
        ]
        assert report.passed is False

    def test_passed_empty_results(self):
        """passed is True when there are no results (vacuously true)."""
        report = ValidationReport(stage="test")
        assert report.passed is True

    def test_failed_rules_returns_only_failures(self):
        """failed_rules returns only results where passed=False."""
        report = ValidationReport(stage="test")
        r_fail = ValidationResult(rule_name="r2", passed=False, message="bad")
        report.results = [
            ValidationResult(rule_name="r1", passed=True, message="ok"),
            r_fail,
        ]
        assert report.failed_rules == [r_fail]
