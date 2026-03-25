"""Tests for combined portfolio module."""

from unittest.mock import MagicMock

import pytest

from src.pipeline.combine import CombineError, combine_portfolios


@pytest.fixture()
def mock_storage():
    """Mock storage with crypto and trad portfolios."""
    storage = MagicMock()
    crypto = {
        "weights": {"BTCUSDT": 0.6, "ETHUSDT": 0.4},
        "expected_return": 0.20,
        "volatility": 0.40,
        "sharpe_ratio": 0.50,
    }
    trad = {
        "weights": {"SPY": 0.5, "GLD": 0.3, "TLT": 0.2},
        "expected_return": 0.10,
        "volatility": 0.15,
        "sharpe_ratio": 0.67,
    }

    def _load(key: str) -> dict:
        return {"weights": crypto, "weights_trad": trad}[key]

    storage.load_output.side_effect = _load
    return storage


class TestCombinePortfolios:
    """Tests for combine_portfolios function."""

    def test_default_60_40_split(self, mock_storage):
        result = combine_portfolios(storage=mock_storage, save=False)
        assert result["allocation"]["crypto"] == 0.6
        assert result["allocation"]["traditional"] == pytest.approx(0.4)

    def test_combined_weights_sum_to_one(self, mock_storage):
        result = combine_portfolios(storage=mock_storage, save=False)
        total = sum(result["weights"].values())
        assert total == pytest.approx(1.0, abs=1e-4)

    def test_crypto_weights_scaled(self, mock_storage):
        result = combine_portfolios(crypto_weight=0.6, storage=mock_storage, save=False)
        assert result["weights"]["BTCUSDT"] == pytest.approx(0.36, abs=1e-4)
        assert result["weights"]["ETHUSDT"] == pytest.approx(0.24, abs=1e-4)

    def test_trad_weights_scaled(self, mock_storage):
        result = combine_portfolios(crypto_weight=0.6, storage=mock_storage, save=False)
        assert result["weights"]["SPY"] == pytest.approx(0.20, abs=1e-4)
        assert result["weights"]["GLD"] == pytest.approx(0.12, abs=1e-4)

    def test_blended_return(self, mock_storage):
        result = combine_portfolios(crypto_weight=0.6, storage=mock_storage, save=False)
        expected = 0.6 * 0.20 + 0.4 * 0.10
        assert result["expected_return"] == pytest.approx(expected, abs=1e-4)

    def test_blended_volatility(self, mock_storage):
        result = combine_portfolios(crypto_weight=0.6, storage=mock_storage, save=False)
        expected = (0.6**2 * 0.40**2 + 0.4**2 * 0.15**2) ** 0.5
        assert result["volatility"] == pytest.approx(expected, abs=1e-4)

    def test_sharpe_ratio_computed(self, mock_storage):
        result = combine_portfolios(storage=mock_storage, save=False)
        assert result["sharpe_ratio"] > 0

    def test_sub_portfolio_metrics_preserved(self, mock_storage):
        result = combine_portfolios(storage=mock_storage, save=False)
        assert result["crypto_metrics"]["expected_return"] == 0.20
        assert result["trad_metrics"]["expected_return"] == 0.10

    def test_symbol_lists(self, mock_storage):
        result = combine_portfolios(storage=mock_storage, save=False)
        assert set(result["crypto_symbols"]) == {"BTCUSDT", "ETHUSDT"}
        assert set(result["trad_symbols"]) == {"SPY", "GLD", "TLT"}

    def test_100_pct_crypto(self, mock_storage):
        result = combine_portfolios(crypto_weight=1.0, storage=mock_storage, save=False)
        assert result["weights"]["BTCUSDT"] == pytest.approx(0.6, abs=1e-4)
        assert result["weights"].get("SPY", 0) == pytest.approx(0.0, abs=1e-6)

    def test_100_pct_trad(self, mock_storage):
        result = combine_portfolios(crypto_weight=0.0, storage=mock_storage, save=False)
        assert result["weights"].get("BTCUSDT", 0) == pytest.approx(0.0, abs=1e-6)
        assert result["weights"]["SPY"] == pytest.approx(0.5, abs=1e-4)

    def test_save_to_storage(self, mock_storage):
        combine_portfolios(storage=mock_storage, save=True)
        mock_storage.save_output.assert_called_once()
        args = mock_storage.save_output.call_args
        assert args[0][1] == "weights_combined"

    def test_invalid_crypto_weight_negative(self, mock_storage):
        with pytest.raises(CombineError, match="between 0 and 1"):
            combine_portfolios(crypto_weight=-0.1, storage=mock_storage)

    def test_invalid_crypto_weight_above_one(self, mock_storage):
        with pytest.raises(CombineError, match="between 0 and 1"):
            combine_portfolios(crypto_weight=1.5, storage=mock_storage)

    def test_missing_crypto_portfolio(self):
        storage = MagicMock()
        storage.load_output.side_effect = FileNotFoundError("not found")
        with pytest.raises(CombineError, match="Crypto portfolio not found"):
            combine_portfolios(storage=storage)

    def test_missing_trad_portfolio(self):
        storage = MagicMock()

        def _load(key: str) -> dict:
            if key == "weights":
                return {"weights": {"BTC": 0.5}}
            raise FileNotFoundError("not found")

        storage.load_output.side_effect = _load
        with pytest.raises(CombineError, match="Traditional portfolio not found"):
            combine_portfolios(storage=storage)

    def test_empty_crypto_weights(self):
        storage = MagicMock()

        def _load(key: str) -> dict:
            if key == "weights":
                return {"weights": {}}
            return {"weights": {"SPY": 1.0}}

        storage.load_output.side_effect = _load
        with pytest.raises(CombineError, match="no weights"):
            combine_portfolios(storage=storage)
