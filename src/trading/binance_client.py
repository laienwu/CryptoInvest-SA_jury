"""
Signed Binance REST client — testnet only.

The **mainnet hard-block** is the safety invariant of this module. The
constructor refuses to run if ``base_url`` does not resolve to the
Binance testnet, so a misconfigured environment fails at import-time
rather than at order-time.

Dry-run posture (``dry_run=True``) mocks *write* endpoints only
(``place_market_order``, ``place_stop_loss_limit``, ``cancel_order``).
Read endpoints still hit the live testnet, so equity / filters /
reconciliation see real state even in a rehearsal.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import time
import urllib.parse
import uuid
from typing import Any
from urllib.parse import urlparse

import requests

from src.pipeline.ingest import BinanceAPIError, make_binance_request
from src.trading.errors import MainnetBlockedError

logger = logging.getLogger(__name__)

RETRY_DELAY_MULTIPLIER: float = 2.0

# Hosts considered testnet. Anything else is refused at init.
_TESTNET_HOSTS: frozenset[str] = frozenset({
    "testnet.binance.vision",
    "testnet.binancefuture.com",
})


def _is_testnet_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except (ValueError, AttributeError):
        return False
    return host in _TESTNET_HOSTS


class BinanceClient:
    """Minimal signed Binance client, hard-locked to testnet."""

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str,
        *,
        dry_run: bool = True,
        rate_limit_delay: float = 0.5,
        max_retries: int = 3,
        recv_window_ms: int = 5000,
    ):
        if not _is_testnet_url(base_url):
            raise MainnetBlockedError(
                f"Refusing to init BinanceClient: {base_url!r} is not a testnet host"
            )
        if not api_key or not api_secret:
            # Signed endpoints will fail without creds; surface early.
            raise MainnetBlockedError(
                "Refusing to init BinanceClient: API key/secret not set "
                "(set BINANCE_TESTNET_API_KEY / BINANCE_TESTNET_API_SECRET)"
            )

        self.api_key = api_key
        self._api_secret = api_secret.encode("utf-8")
        self.base_url = base_url.rstrip("/")
        self.dry_run = dry_run
        self.rate_limit_delay = rate_limit_delay
        self.max_retries = max_retries
        self.recv_window_ms = recv_window_ms
        # Offset (ms) added to the local timestamp on every signed request so
        # Binance's recvWindow check accepts us despite local clock drift. Stays
        # at 0 until ``sync_time()`` is called; the tick syncs once per run.
        self._time_offset_ms: int = 0

    # -- internals -----------------------------------------------------------

    def _sign(self, query_string: str) -> str:
        return hmac.new(self._api_secret, query_string.encode("utf-8"),
                        hashlib.sha256).hexdigest()

    def _headers(self) -> dict[str, str]:
        return {"X-MBX-APIKEY": self.api_key}

    def signed_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """
        Send a signed request to a Binance SAPI/API v3 endpoint.

        Retries on 429 with ``Retry-After`` and on transient network errors
        with exponential backoff.
        """
        params = dict(params or {})
        params.setdefault("recvWindow", self.recv_window_ms)
        params["timestamp"] = int(time.time() * 1000) + self._time_offset_ms

        query = urllib.parse.urlencode(params, doseq=True)
        signature = self._sign(query)
        url = f"{self.base_url}{path}?{query}&signature={signature}"

        delay = self.rate_limit_delay
        last_exc: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = requests.request(
                    method, url, headers=self._headers(), timeout=30
                )
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning("Rate limited on %s %s, sleeping %ds",
                                   method, path, retry_after)
                    time.sleep(retry_after)
                    continue
                if response.status_code != 200:
                    try:
                        msg = response.json().get("msg", response.text[:200])
                    except ValueError:
                        msg = response.text[:200]
                    raise BinanceAPIError(
                        f"{method} {path} failed: {msg}",
                        status_code=response.status_code,
                    )
                return response.json()

            except requests.exceptions.RequestException as e:
                last_exc = BinanceAPIError(f"{method} {path} network error: {e}")
                logger.warning("Network error on attempt %d/%d: %s",
                               attempt + 1, self.max_retries, e)

            if attempt < self.max_retries - 1:
                time.sleep(delay)
                delay *= RETRY_DELAY_MULTIPLIER

        raise last_exc or BinanceAPIError(f"{method} {path} failed after retries")

    # -- public (unsigned) ---------------------------------------------------

    def get_server_time(self) -> int:
        """Unsigned GET /api/v3/time — used to calibrate the local clock offset."""
        url = f"{self.base_url}/api/v3/time"
        data = make_binance_request(
            url, {},
            rate_limit_delay=self.rate_limit_delay,
            max_retries=self.max_retries,
        )
        assert isinstance(data, dict)
        return int(data["serverTime"])

    def sync_time(self) -> None:
        """
        Calibrate ``_time_offset_ms`` against Binance's server clock.

        Binance rejects signed requests whose timestamp is more than ~1s
        ahead of server time (recvWindow only cushions *lagging* clocks).
        Callers (the tick) should invoke this once per run so the client
        survives OS-level clock drift.

        Failure is non-fatal: the offset stays at its previous value and
        signed requests proceed. If the clock is already close enough,
        they'll succeed; if not, the underlying timestamp error propagates
        with the same signal a caller would get today.
        """
        try:
            server_ms = self.get_server_time()
        except BinanceAPIError as e:
            logger.warning("sync_time: /api/v3/time failed, offset stays at %dms: %s",
                           self._time_offset_ms, e)
            return
        local_ms = int(time.time() * 1000)
        self._time_offset_ms = server_ms - local_ms
        logger.info("sync_time: offset=%+dms (local=%d, server=%d)",
                    self._time_offset_ms, local_ms, server_ms)

    def get_exchange_info(self, symbols: list[str] | None = None) -> dict[str, Any]:
        """Fetch ``/api/v3/exchangeInfo`` (unsigned, cached by caller)."""
        params: dict[str, Any] = {}
        if symbols:
            # exchangeInfo expects a JSON-array string literal for the ``symbols`` param.
            params["symbols"] = '["' + '","'.join(symbols) + '"]'
        url = f"{self.base_url}/api/v3/exchangeInfo"
        data = make_binance_request(
            url, params,
            rate_limit_delay=self.rate_limit_delay,
            max_retries=self.max_retries,
        )
        assert isinstance(data, dict)
        return data

    # -- account / positions -------------------------------------------------

    def get_account(self) -> dict[str, Any]:
        """Signed GET /api/v3/account — balances and trading status."""
        result = self.signed_request("GET", "/api/v3/account")
        assert isinstance(result, dict)
        return result

    def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """Signed GET /api/v3/openOrders."""
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        result = self.signed_request("GET", "/api/v3/openOrders", params)
        assert isinstance(result, list)
        return result

    def get_my_trades(
        self,
        symbol: str,
        start_time_ms: int | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Signed GET /api/v3/myTrades."""
        params: dict[str, Any] = {"symbol": symbol, "limit": limit}
        if start_time_ms is not None:
            params["startTime"] = start_time_ms
        result = self.signed_request("GET", "/api/v3/myTrades", params)
        assert isinstance(result, list)
        return result

    def get_order(
        self,
        symbol: str,
        order_id: str | None = None,
        orig_client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Signed GET /api/v3/order — look up a single order."""
        if not order_id and not orig_client_order_id:
            raise ValueError("get_order requires order_id or orig_client_order_id")
        params: dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        result = self.signed_request("GET", "/api/v3/order", params)
        assert isinstance(result, dict)
        return result

    # -- orders (writes — dry-run aware) -------------------------------------

    def place_market_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        client_order_id: str,
    ) -> dict[str, Any]:
        """Signed POST /api/v3/order — type=MARKET. Mocked in dry-run."""
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": _format_qty(qty),
            "newClientOrderId": client_order_id,
        }
        if self.dry_run:
            logger.info("[dry-run] place_market_order %s", params)
            return _mock_order_response(symbol, side, qty, client_order_id, "MARKET")
        return self._post_order(params)

    def place_stop_loss_limit(
        self,
        symbol: str,
        side: str,
        qty: float,
        stop_price: float,
        limit_price: float,
        client_order_id: str,
    ) -> dict[str, Any]:
        """
        Signed POST /api/v3/order — type=STOP_LOSS_LIMIT.

        Sits on the exchange as the safety net: even if the tick crashes,
        Binance will trigger the stop on its own.
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": "STOP_LOSS_LIMIT",
            "timeInForce": "GTC",
            "quantity": _format_qty(qty),
            "stopPrice": _format_price(stop_price),
            "price": _format_price(limit_price),
            "newClientOrderId": client_order_id,
        }
        if self.dry_run:
            logger.info("[dry-run] place_stop_loss_limit %s", params)
            return _mock_order_response(symbol, side, qty, client_order_id,
                                        "STOP_LOSS_LIMIT", stop_price=stop_price)
        return self._post_order(params)

    def cancel_order(
        self,
        symbol: str,
        order_id: str | None = None,
        orig_client_order_id: str | None = None,
    ) -> dict[str, Any]:
        """Signed DELETE /api/v3/order. Mocked in dry-run."""
        if not order_id and not orig_client_order_id:
            raise ValueError("cancel_order requires order_id or orig_client_order_id")
        params: dict[str, Any] = {"symbol": symbol}
        if order_id:
            params["orderId"] = order_id
        if orig_client_order_id:
            params["origClientOrderId"] = orig_client_order_id
        if self.dry_run:
            logger.info("[dry-run] cancel_order %s", params)
            return {"symbol": symbol, "status": "CANCELED", "dry_run": True}
        result = self.signed_request("DELETE", "/api/v3/order", params)
        assert isinstance(result, dict)
        return result

    def _post_order(self, params: dict[str, Any]) -> dict[str, Any]:
        result = self.signed_request("POST", "/api/v3/order", params)
        assert isinstance(result, dict)
        return result


# -- helpers -----------------------------------------------------------------


def new_client_order_id(prefix: str = "bot") -> str:
    """
    Deterministic-ish idempotency key.

    Binance allows up to 36 chars, alphanumeric + ``-`` / ``_``. We use a
    short prefix + hex UUID to stay well under the limit.
    """
    return f"{prefix}-{uuid.uuid4().hex[:24]}"


def _format_qty(qty: float) -> str:
    # Binance rejects scientific notation; strip trailing zeros for a clean wire format.
    s = f"{qty:.8f}".rstrip("0").rstrip(".")
    return s or "0"


def _format_price(price: float) -> str:
    s = f"{price:.8f}".rstrip("0").rstrip(".")
    return s or "0"


def _mock_order_response(
    symbol: str,
    side: str,
    qty: float,
    client_order_id: str,
    order_type: str,
    stop_price: float | None = None,
) -> dict[str, Any]:
    """Shape mirrors Binance so downstream parsing is unchanged in dry-run."""
    ts_ms = int(time.time() * 1000)
    resp: dict[str, Any] = {
        "symbol": symbol,
        "orderId": f"dry-{ts_ms}",
        "clientOrderId": client_order_id,
        "transactTime": ts_ms,
        "status": "FILLED" if order_type == "MARKET" else "NEW",
        "type": order_type,
        "side": side,
        "origQty": _format_qty(qty),
        "executedQty": _format_qty(qty) if order_type == "MARKET" else "0",
        "dry_run": True,
    }
    if stop_price is not None:
        resp["stopPrice"] = _format_price(stop_price)
    return resp
