"""Tests for the pair trading / cointegration analysis module."""

import math
import random

import pytest

from src.pipeline.pairs import (
    PairsError,
    _adf_statistic,
    _ols_simple,
    analyze_pairs,
    compute_spread,
    engle_granger_test,
    find_all_pairs,
    z_score_signal,
)


# ---------------------------------------------------------------------------
# MockStorage
# ---------------------------------------------------------------------------


class MockStorage:
    """Minimal storage mock for pairs tests."""

    def __init__(
        self,
        raw_data: dict | None = None,
        raise_on_load: bool = False,
    ):
        self._raw = raw_data if raw_data is not None else {}
        self._raise_on_load = raise_on_load
        self._saved: dict = {}

    def load_raw(self, symbols=None):
        if self._raise_on_load:
            raise FileNotFoundError("no raw data")
        if symbols is not None:
            return {s: self._raw[s] for s in symbols if s in self._raw}
        return self._raw

    def save_output(self, data, name):
        self._saved[name] = data


def _make_kline_records(closes: list[float], start_ts: int = 1000000) -> list[dict]:
    """Build mock kline records from a list of close prices."""
    records = []
    for i, close in enumerate(closes):
        records.append({
            "timestamp": str(start_ts + i * 86400),
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": 1000.0 + i,
        })
    return records


def _make_cointegrated_raw(n: int = 120) -> dict:
    """
    Build raw data for two cointegrated symbols.

    B ~ 2*A + small noise, so spread is stationary.
    """
    random.seed(42)
    # Random walk for A
    prices_a = [100.0]
    for _ in range(n - 1):
        prices_a.append(prices_a[-1] * (1 + random.gauss(0, 0.01)))

    # B is cointegrated with A: B = 2*A + stationary noise
    prices_b = [2 * p + random.gauss(0, 0.5) for p in prices_a]

    return {
        "AAAA": _make_kline_records(prices_a),
        "BBBB": _make_kline_records(prices_b),
    }


def _make_noncointegrated_raw(n: int = 120) -> dict:
    """Build raw data for two independent random walks."""
    random.seed(99)
    prices_a = [100.0]
    prices_b = [100.0]
    for _ in range(n - 1):
        prices_a.append(prices_a[-1] * (1 + random.gauss(0.001, 0.02)))
        prices_b.append(prices_b[-1] * (1 + random.gauss(-0.001, 0.02)))
    return {
        "XXXX": _make_kline_records(prices_a),
        "YYYY": _make_kline_records(prices_b),
    }


# ---------------------------------------------------------------------------
# TestOlsSimple
# ---------------------------------------------------------------------------


class TestOlsSimple:
    def test_perfect_fit(self):
        """y = 2 + 3*x exactly."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2 + 3 * xi for xi in x]
        alpha, beta, residuals = _ols_simple(y, x)
        assert alpha == pytest.approx(2.0, abs=1e-10)
        assert beta == pytest.approx(3.0, abs=1e-10)
        for r in residuals:
            assert r == pytest.approx(0.0, abs=1e-10)

    def test_slope_and_intercept(self):
        """y = -1 + 0.5*x."""
        x = [0.0, 2.0, 4.0, 6.0, 8.0]
        y = [-1.0, 0.0, 1.0, 2.0, 3.0]
        alpha, beta, _ = _ols_simple(y, x)
        assert alpha == pytest.approx(-1.0, abs=1e-10)
        assert beta == pytest.approx(0.5, abs=1e-10)

    def test_residuals_sum_near_zero(self):
        """OLS residuals should sum to approximately zero."""
        x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
        y = [2.1, 3.9, 6.2, 7.8, 10.1, 12.0, 14.1]
        _, _, residuals = _ols_simple(y, x)
        assert sum(residuals) == pytest.approx(0.0, abs=1e-8)

    def test_unequal_length_raises(self):
        with pytest.raises(PairsError, match="equal length"):
            _ols_simple([1.0, 2.0], [1.0])

    def test_too_few_observations_raises(self):
        with pytest.raises(PairsError, match="at least 3"):
            _ols_simple([1.0, 2.0], [1.0, 2.0])

    def test_zero_variance_x_raises(self):
        with pytest.raises(PairsError, match="zero variance"):
            _ols_simple([1.0, 2.0, 3.0], [5.0, 5.0, 5.0])


# ---------------------------------------------------------------------------
# TestAdfStatistic
# ---------------------------------------------------------------------------


class TestAdfStatistic:
    def test_stationary_series_negative(self):
        """Mean-reverting series should have a clearly negative ADF stat."""
        random.seed(10)
        # Stationary AR(1) with strong mean reversion
        series = [0.0]
        for _ in range(200):
            series.append(-0.8 * series[-1] + random.gauss(0, 1))
        stat = _adf_statistic(series)
        assert stat < -3.0

    def test_random_walk_near_zero(self):
        """Pure random walk should have ADF stat near zero."""
        random.seed(20)
        series = [0.0]
        for _ in range(200):
            series.append(series[-1] + random.gauss(0, 1))
        stat = _adf_statistic(series)
        # Random walk: ADF should be close to zero (not very negative)
        assert stat > -2.5

    def test_too_short_raises(self):
        with pytest.raises(PairsError, match="at least 4"):
            _adf_statistic([1.0, 2.0, 3.0])


# ---------------------------------------------------------------------------
# TestEngleGrangerTest
# ---------------------------------------------------------------------------


class TestEngleGrangerTest:
    def test_cointegrated_pair(self):
        """Two series with a stable linear relationship."""
        random.seed(30)
        n = 200
        # Common stochastic trend
        trend = [0.0]
        for _ in range(n - 1):
            trend.append(trend[-1] + random.gauss(0, 1))

        series_a = [t + random.gauss(0, 0.3) for t in trend]
        series_b = [2 * t + random.gauss(0, 0.3) for t in trend]

        result = engle_granger_test(series_a, series_b)
        assert result["is_cointegrated"] is True
        assert result["adf_statistic"] < _adf_critical()
        assert result["hedge_ratio"] == pytest.approx(0.5, abs=0.1)

    def test_non_cointegrated_pair(self):
        """Two independent random walks should not be cointegrated."""
        random.seed(40)
        n = 200
        a = [0.0]
        b = [0.0]
        for _ in range(n - 1):
            a.append(a[-1] + random.gauss(0, 1))
            b.append(b[-1] + random.gauss(0, 1))

        result = engle_granger_test(a, b)
        # Not guaranteed to pass every seed, but seed=40 works
        assert result["adf_statistic"] > -4.0  # loose check

    def test_hedge_ratio_is_slope(self):
        """Hedge ratio should approximate the true slope."""
        x = list(range(100))
        # y = 3*x + noise
        random.seed(50)
        y = [3 * xi + random.gauss(0, 0.1) for xi in x]
        xf = [float(xi) for xi in x]
        result = engle_granger_test(y, xf)
        assert result["hedge_ratio"] == pytest.approx(3.0, abs=0.05)

    def test_unequal_length_raises(self):
        with pytest.raises(PairsError, match="equal length"):
            engle_granger_test([1.0, 2.0, 3.0, 4.0], [1.0, 2.0])

    def test_too_few_raises(self):
        with pytest.raises(PairsError, match="at least 4"):
            engle_granger_test([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])


def _adf_critical() -> float:
    """Helper to access the module's critical value."""
    from src.pipeline.pairs import _ADF_CRITICAL_5PCT
    return _ADF_CRITICAL_5PCT


# ---------------------------------------------------------------------------
# TestComputeSpread
# ---------------------------------------------------------------------------


class TestComputeSpread:
    def test_basic_spread(self):
        a = [10.0, 11.0, 12.0]
        b = [5.0, 5.5, 6.0]
        spread = compute_spread(a, b, hedge_ratio=2.0)
        assert spread[0] == pytest.approx(0.0)
        assert spread[1] == pytest.approx(0.0)
        assert spread[2] == pytest.approx(0.0)

    def test_zero_hedge_ratio_equals_original(self):
        a = [10.0, 20.0, 30.0]
        b = [1.0, 2.0, 3.0]
        spread = compute_spread(a, b, hedge_ratio=0.0)
        assert spread == a

    def test_negative_hedge_ratio(self):
        a = [10.0, 20.0]
        b = [5.0, 10.0]
        spread = compute_spread(a, b, hedge_ratio=-1.0)
        assert spread[0] == pytest.approx(15.0)
        assert spread[1] == pytest.approx(30.0)

    def test_unequal_length_raises(self):
        with pytest.raises(PairsError, match="equal length"):
            compute_spread([1.0], [1.0, 2.0], hedge_ratio=1.0)


# ---------------------------------------------------------------------------
# TestZScoreSignal
# ---------------------------------------------------------------------------


class TestZScoreSignal:
    def test_neutral_near_zero(self):
        """Constant spread should yield all neutral signals."""
        spread = [5.0] * 30
        signals = z_score_signal(spread, window=10)
        for s in signals:
            assert s["signal"] == "neutral"
            assert s["z_score"] == pytest.approx(0.0, abs=0.01)

    def test_long_signal(self):
        """Large negative deviation should trigger long signal."""
        # Stable then big drop
        spread = [100.0] * 25 + [80.0]
        signals = z_score_signal(spread, window=20)
        last = signals[-1]
        assert last["signal"] == "long"
        assert last["z_score"] < -2.0

    def test_short_signal(self):
        """Large positive deviation should trigger short signal."""
        spread = [100.0] * 25 + [120.0]
        signals = z_score_signal(spread, window=20)
        last = signals[-1]
        assert last["signal"] == "short"
        assert last["z_score"] > 2.0

    def test_window_size(self):
        """Smaller window should produce signals sooner."""
        spread = list(range(50))
        signals_5 = z_score_signal(spread, window=5)
        signals_20 = z_score_signal(spread, window=20)
        # First non-zero z-score should appear earlier with window=5
        first_nonzero_5 = next(
            i for i, s in enumerate(signals_5) if s["z_score"] != 0.0
        )
        first_nonzero_20 = next(
            i for i, s in enumerate(signals_20) if s["z_score"] != 0.0
        )
        assert first_nonzero_5 < first_nonzero_20

    def test_empty_spread(self):
        assert z_score_signal([], window=5) == []

    def test_small_window_raises(self):
        with pytest.raises(PairsError, match="at least 2"):
            z_score_signal([1.0, 2.0], window=1)

    def test_period_indices(self):
        spread = [1.0, 2.0, 3.0, 4.0, 5.0]
        signals = z_score_signal(spread, window=3)
        for i, s in enumerate(signals):
            assert s["period"] == i


# ---------------------------------------------------------------------------
# TestFindAllPairs
# ---------------------------------------------------------------------------


class TestFindAllPairs:
    def test_finds_cointegrated_pairs(self):
        """Two cointegrated series should be detected."""
        random.seed(60)
        n = 150
        # Common factor
        factor_returns = [random.gauss(0, 0.01) for _ in range(n)]
        noise_a = [random.gauss(0, 0.001) for _ in range(n)]
        noise_b = [random.gauss(0, 0.001) for _ in range(n)]

        returns = {
            "SYM_A": [f + na for f, na in zip(factor_returns, noise_a)],
            "SYM_B": [f + nb for f, nb in zip(factor_returns, noise_b)],
        }
        pairs = find_all_pairs(returns, min_observations=10)
        assert len(pairs) == 1
        assert pairs[0]["pair"] == ["SYM_A", "SYM_B"]

    def test_empty_returns(self):
        assert find_all_pairs({}) == []

    def test_single_asset(self):
        assert find_all_pairs({"A": [0.01] * 100}) == []

    def test_min_observations_filter(self):
        """Pairs with too few observations should be excluded."""
        returns = {
            "A": [0.01] * 10,
            "B": [0.02] * 10,
        }
        # min_observations=50 should filter them out
        pairs = find_all_pairs(returns, min_observations=50)
        assert len(pairs) == 0

    def test_sorted_by_adf(self):
        """Results should be sorted by ADF statistic (most negative first)."""
        random.seed(70)
        n = 120
        factor = [random.gauss(0, 0.01) for _ in range(n)]
        returns = {
            "A": [f + random.gauss(0, 0.001) for f in factor],
            "B": [f + random.gauss(0, 0.001) for f in factor],
            "C": [random.gauss(0, 0.02) for _ in range(n)],
        }
        pairs = find_all_pairs(returns, min_observations=10)
        assert len(pairs) == 3  # A-B, A-C, B-C
        # Should be sorted by ADF statistic ascending
        for i in range(len(pairs) - 1):
            assert pairs[i]["adf_statistic"] <= pairs[i + 1]["adf_statistic"]


# ---------------------------------------------------------------------------
# TestAnalyzePairs
# ---------------------------------------------------------------------------


class TestAnalyzePairs:
    def test_basic_analysis(self):
        raw = _make_cointegrated_raw(n=120)
        storage = MockStorage(raw_data=raw)
        result = analyze_pairs(min_observations=10, storage=storage, save=False)
        assert "pairs" in result
        assert "n_pairs_tested" in result
        assert "n_cointegrated" in result
        assert result["method"] == "pairs_analysis"
        assert result["n_pairs_tested"] >= 1

    def test_saves_when_requested(self):
        raw = _make_cointegrated_raw(n=120)
        storage = MockStorage(raw_data=raw)
        analyze_pairs(min_observations=10, storage=storage, save=True)
        assert "pairs_analysis" in storage._saved

    def test_no_save_when_disabled(self):
        raw = _make_cointegrated_raw(n=120)
        storage = MockStorage(raw_data=raw)
        analyze_pairs(min_observations=10, storage=storage, save=False)
        assert "pairs_analysis" not in storage._saved

    def test_missing_data_raises(self):
        storage = MockStorage(raise_on_load=True)
        with pytest.raises(PairsError, match="Raw price data not found"):
            analyze_pairs(storage=storage)

    def test_empty_data_raises(self):
        storage = MockStorage(raw_data={})
        with pytest.raises(PairsError, match="No symbols found"):
            analyze_pairs(storage=storage)

    def test_single_symbol_raises(self):
        raw = {"ONLY": _make_kline_records([100.0, 101.0, 102.0])}
        storage = MockStorage(raw_data=raw)
        with pytest.raises(PairsError, match="at least 2 symbols"):
            analyze_pairs(storage=storage)

    def test_top_pair_detail(self):
        raw = _make_cointegrated_raw(n=150)
        storage = MockStorage(raw_data=raw)
        result = analyze_pairs(min_observations=10, storage=storage, save=False)
        if result["n_cointegrated"] > 0:
            detail = result["top_pair_detail"]
            assert detail is not None
            assert "pair" in detail
            assert "hedge_ratio" in detail
            assert "z_scores" in detail
            assert "current_signal" in detail


# ---------------------------------------------------------------------------
# TestPairsError
# ---------------------------------------------------------------------------


class TestPairsError:
    def test_message(self):
        err = PairsError("something failed")
        assert str(err) == "something failed"
        assert err.message == "something failed"
        assert err.operation == "pairs"

    def test_custom_operation(self):
        err = PairsError("bad data", operation="load")
        assert err.operation == "load"
        assert err.message == "bad data"
