"""Tests for PDF portfolio report generation."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ``fpdf2`` lives in the optional ``pdf`` extra. CI syncs only ``dev`` +
# ``optimize``, so skip the whole module when the backend isn't installed.
pytest.importorskip("fpdf")

from src.pipeline.pdf_export import PDFExportError, generate_portfolio_report  # noqa: E402


@pytest.fixture()
def mock_storage():
    """Mock storage with portfolio data."""
    storage = MagicMock()
    storage.load_output.return_value = {
        "weights": {"BTCUSDT": 0.50, "ETHUSDT": 0.30, "SOLUSDT": 0.20},
        "expected_return": 0.185,
        "volatility": 0.283,
        "sharpe_ratio": 1.24,
    }
    return storage


class TestGeneratePortfolioReport:
    """Tests for generate_portfolio_report."""

    def test_generates_pdf_file(self, mock_storage, tmp_path):
        out = tmp_path / "report.pdf"
        result = generate_portfolio_report(output_path=out, storage=mock_storage)
        assert Path(result["output_path"]).exists()
        assert out.stat().st_size > 0

    def test_pdf_starts_with_magic_bytes(self, mock_storage, tmp_path):
        out = tmp_path / "report.pdf"
        generate_portfolio_report(output_path=out, storage=mock_storage)
        with open(out, "rb") as f:
            assert f.read(5) == b"%PDF-"

    def test_result_contains_metadata(self, mock_storage, tmp_path):
        out = tmp_path / "report.pdf"
        result = generate_portfolio_report(output_path=out, storage=mock_storage)
        assert result["n_assets"] == 3
        assert result["sharpe_ratio"] == 1.24
        assert result["portfolio_key"] == "weights"

    def test_custom_title(self, mock_storage, tmp_path):
        out = tmp_path / "report.pdf"
        result = generate_portfolio_report(
            output_path=out, title="My Report", storage=mock_storage
        )
        assert result["title"] == "My Report"

    def test_trad_portfolio_key(self, mock_storage, tmp_path):
        out = tmp_path / "report.pdf"
        result = generate_portfolio_report(
            output_path=out, portfolio_key="weights_trad", storage=mock_storage
        )
        assert result["portfolio_key"] == "weights_trad"
        mock_storage.load_output.assert_called_with("weights_trad")

    def test_missing_portfolio_raises_error(self, tmp_path):
        storage = MagicMock()
        storage.load_output.side_effect = FileNotFoundError("not found")
        with pytest.raises(PDFExportError, match="not found"):
            generate_portfolio_report(
                output_path=tmp_path / "report.pdf", storage=storage
            )

    def test_creates_output_directory(self, mock_storage, tmp_path):
        out = tmp_path / "subdir" / "nested" / "report.pdf"
        result = generate_portfolio_report(output_path=out, storage=mock_storage)
        assert Path(result["output_path"]).exists()

    def test_missing_fpdf2_raises_error(self, mock_storage, tmp_path):
        with patch.dict("sys.modules", {"fpdf": None}):
            with pytest.raises(PDFExportError, match="fpdf2 not installed"):
                generate_portfolio_report(
                    output_path=tmp_path / "report.pdf", storage=mock_storage
                )

    def test_empty_weights_generates_pdf(self, tmp_path):
        storage = MagicMock()
        storage.load_output.return_value = {
            "weights": {},
            "expected_return": 0.0,
            "volatility": 0.0,
            "sharpe_ratio": 0.0,
        }
        result = generate_portfolio_report(
            output_path=tmp_path / "report.pdf", storage=storage
        )
        assert result["n_assets"] == 0
        assert Path(result["output_path"]).exists()

    def test_many_assets(self, tmp_path):
        storage = MagicMock()
        weights = {f"ASSET{i}": round(1.0 / 20, 6) for i in range(20)}
        storage.load_output.return_value = {
            "weights": weights,
            "expected_return": 0.10,
            "volatility": 0.20,
            "sharpe_ratio": 0.50,
        }
        result = generate_portfolio_report(
            output_path=tmp_path / "report.pdf", storage=storage
        )
        assert result["n_assets"] == 20

    def test_default_output_path(self, mock_storage):
        with tempfile.TemporaryDirectory() as td:
            default_path = Path(td) / "portfolio_report.pdf"
            with patch(
                "src.pipeline.pdf_export.DEFAULT_OUTPUT_PATH", default_path
            ):
                result = generate_portfolio_report(storage=mock_storage)
                assert Path(result["output_path"]).exists()
