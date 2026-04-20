"""Tests for src/trading/binance_client.py — mainnet block, signing, dry-run."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any
from unittest.mock import patch

import pytest

from src.trading.binance_client import (
    BinanceClient,
    _format_price,
    _format_qty,
    _is_testnet_url,
    new_client_order_id,
)
from src.trading.errors import MainnetBlockedError


def _client(dry_run: bool = True) -> BinanceClient:
    return BinanceClient(
        api_key="test-key",
        api_secret="test-secret",
        base_url="https://testnet.binance.vision",
        dry_run=dry_run,
    )


def test_mainnet_url_blocked() -> None:
    with pytest.raises(MainnetBlockedError):
        BinanceClient("k", "s", "https://api.binance.com", dry_run=True)


def test_missing_credentials_blocked() -> None:
    with pytest.raises(MainnetBlockedError):
        BinanceClient("", "", "https://testnet.binance.vision", dry_run=True)


def test_is_testnet_url_detects_hosts() -> None:
    assert _is_testnet_url("https://testnet.binance.vision/foo")
    assert _is_testnet_url("https://testnet.binancefuture.com/bar")
    assert not _is_testnet_url("https://api.binance.com")
    assert not _is_testnet_url("not-a-url")


def test_signing_matches_hmac_sha256() -> None:
    client = _client()
    query = "symbol=BTCUSDT&timestamp=1"
    expected = hmac.new(b"test-secret", query.encode(), hashlib.sha256).hexdigest()
    assert client._sign(query) == expected


def test_dry_run_market_order_returns_synthetic_fill() -> None:
    client = _client(dry_run=True)
    resp = client.place_market_order("BTCUSDT", "BUY", 0.5, "coid-1")
    assert resp["dry_run"] is True
    assert resp["status"] == "FILLED"
    assert resp["clientOrderId"] == "coid-1"
    assert resp["executedQty"] == "0.5"


def test_dry_run_stop_loss_limit_has_stop_price() -> None:
    client = _client(dry_run=True)
    resp = client.place_stop_loss_limit("BTCUSDT", "SELL", 0.5, 95.0, 94.0, "stop-1")
    assert resp["dry_run"] is True
    assert resp["status"] == "NEW"
    assert resp["stopPrice"] == "95"


def test_dry_run_cancel_order_short_circuits() -> None:
    client = _client(dry_run=True)
    resp = client.cancel_order("BTCUSDT", orig_client_order_id="coid-1")
    assert resp["dry_run"] is True
    assert resp["status"] == "CANCELED"


def test_format_qty_strips_trailing_zeros() -> None:
    assert _format_qty(1.5) == "1.5"
    assert _format_qty(0.12340000) == "0.1234"
    assert _format_qty(1.0) == "1"


def test_format_price_strips_trailing_zeros() -> None:
    assert _format_price(100.0) == "100"
    assert _format_price(0.00001234) == "0.00001234"


def test_new_client_order_id_prefixed_and_unique() -> None:
    a = new_client_order_id("bot")
    b = new_client_order_id("bot")
    assert a.startswith("bot-") and b.startswith("bot-")
    assert a != b
    assert len(a) <= 36


def test_signed_request_hits_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    """signed_request should append timestamp + signature and call requests.request."""
    captured: dict[str, Any] = {}

    class FakeResp:
        status_code = 200
        headers: dict[str, str] = {}
        def json(self) -> dict[str, Any]:
            return {"balances": []}

    def fake_request(method: str, url: str, headers: dict[str, str], timeout: int) -> FakeResp:
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        return FakeResp()

    client = _client(dry_run=False)
    with patch("src.trading.binance_client.requests.request", side_effect=fake_request):
        client.get_account()
    assert captured["method"] == "GET"
    assert "/api/v3/account" in captured["url"]
    assert "signature=" in captured["url"]
    assert "timestamp=" in captured["url"]
    assert captured["headers"]["X-MBX-APIKEY"] == "test-key"
