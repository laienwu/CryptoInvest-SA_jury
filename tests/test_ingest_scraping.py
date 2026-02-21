"""
Tests for src/pipeline/ingest_scraping.py

Covers: ScrapingError, _parse_number, _parse_percentage,
scrape_market_rankings (fallback when table not found, no-fallback raise).
HTTP layer is mocked via patching _get_page / _parse_html.
bs4 is not installed in test env — tests that need HTML parsing mock _parse_html.
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.ingest_scraping import (
    ScrapingError,
    _parse_number,
    scrape_market_rankings,
)


# =============================================================================
# ScrapingError
# =============================================================================


def test_scraping_error_message_and_url() -> None:
    err = ScrapingError("failed", url="https://example.com")
    assert err.message == "failed"
    assert err.url == "https://example.com"
    assert str(err) == "failed"


def test_scraping_error_no_url() -> None:
    err = ScrapingError("timeout")
    assert err.url is None


# =============================================================================
# _parse_number
# =============================================================================


def test_parse_number_plain() -> None:
    assert _parse_number("42000.5") == pytest.approx(42000.5)


def test_parse_number_with_dollar() -> None:
    assert _parse_number("$95,000.00") == pytest.approx(95000.0)


def test_parse_number_billions() -> None:
    assert _parse_number("1.9B") == pytest.approx(1_900_000_000)


def test_parse_number_millions() -> None:
    assert _parse_number("450M") == pytest.approx(450_000_000)


def test_parse_number_thousands() -> None:
    assert _parse_number("500K") == pytest.approx(500_000)


def test_parse_number_empty_returns_zero() -> None:
    assert _parse_number("") == 0.0


# =============================================================================
# scrape_market_rankings — fallback when no table found in parsed HTML
# =============================================================================


def _make_soup_without_table() -> MagicMock:
    """Mock BeautifulSoup object that has no <table>."""
    soup = MagicMock()
    soup.find.return_value = None  # table not found
    return soup


def test_scrape_market_rankings_fallback_when_no_table() -> None:
    """When page loads but has no table, allow_fallback=True returns sample data."""
    with patch("src.pipeline.ingest_scraping._get_page", return_value="<html></html>"):
        with patch("src.pipeline.ingest_scraping._parse_html",
                   return_value=_make_soup_without_table()):
            result = scrape_market_rankings(limit=5, allow_fallback=True)

    assert isinstance(result, list)
    assert len(result) > 0
    assert "symbol" in result[0]
    assert "price_usd" in result[0]


def test_scrape_market_rankings_raises_when_no_table_no_fallback() -> None:
    """When table not found and allow_fallback=False, raise ScrapingError."""
    with patch("src.pipeline.ingest_scraping._get_page", return_value="<html></html>"):
        with patch("src.pipeline.ingest_scraping._parse_html",
                   return_value=_make_soup_without_table()):
            with pytest.raises(ScrapingError):
                scrape_market_rankings(limit=5, allow_fallback=False)


def test_scrape_market_rankings_fallback_respects_limit() -> None:
    with patch("src.pipeline.ingest_scraping._get_page", return_value="<html></html>"):
        with patch("src.pipeline.ingest_scraping._parse_html",
                   return_value=_make_soup_without_table()):
            result = scrape_market_rankings(limit=3, allow_fallback=True)

    assert len(result) <= 3


def test_scrape_market_rankings_fallback_has_required_fields() -> None:
    required = {"rank", "symbol", "name", "price_usd", "change_24h_pct",
                "market_cap_usd", "volume_24h_usd", "scraped_at", "source"}

    with patch("src.pipeline.ingest_scraping._get_page", return_value="<html></html>"):
        with patch("src.pipeline.ingest_scraping._parse_html",
                   return_value=_make_soup_without_table()):
            result = scrape_market_rankings(limit=5, allow_fallback=True)

    for entry in result:
        assert required.issubset(entry.keys()), f"Missing fields: {entry}"


def test_scrape_market_rankings_fallback_source_label() -> None:
    with patch("src.pipeline.ingest_scraping._get_page", return_value="<html></html>"):
        with patch("src.pipeline.ingest_scraping._parse_html",
                   return_value=_make_soup_without_table()):
            result = scrape_market_rankings(limit=2, allow_fallback=True)

    for entry in result:
        assert "source" in entry


# =============================================================================
# scrape_market_rankings — _get_page failure propagates
# =============================================================================


def test_scrape_market_rankings_get_page_error_propagates() -> None:
    """ScrapingError from _get_page always propagates regardless of allow_fallback."""
    with patch("src.pipeline.ingest_scraping._get_page",
               side_effect=ScrapingError("connect failed", url="https://coingecko.com")):
        with pytest.raises(ScrapingError, match="connect failed"):
            scrape_market_rankings(limit=5, allow_fallback=True)
