"""
Kafka producer for real-time Binance kline streaming.

Connects to Binance WebSocket and publishes kline (candlestick) events
to a Kafka topic for downstream consumption.

Usage:
    python -m src.pipeline.stream_producer

Architecture:
    Binance WebSocket → stream_producer → Kafka topic (klines-raw)
"""

import json
import logging
import os
import signal
import time
from datetime import UTC, datetime
from typing import Any

import websocket
from kafka import KafkaProducer

from src.config import load_config

logger = logging.getLogger(__name__)

BINANCE_WS_BASE = "wss://stream.binance.com:9443/ws"


def _build_stream_url(symbols: list[str], interval: str = "1d") -> str:
    """Build Binance combined WebSocket stream URL."""
    streams = [f"{s.lower()}@kline_{interval}" for s in symbols]
    return f"{BINANCE_WS_BASE}/{'/'.join(streams)}"


def _parse_kline_event(data: dict[str, Any]) -> dict[str, Any] | None:
    """Parse a Binance kline WebSocket event into a flat record."""
    if data.get("e") != "kline":
        return None

    k = data["k"]
    if not k.get("x"):  # Only closed candles
        return None

    return {
        "symbol": k["s"],
        "timestamp": datetime.fromtimestamp(k["t"] / 1000, tz=UTC).strftime("%Y-%m-%d"),
        "open": float(k["o"]),
        "high": float(k["h"]),
        "low": float(k["l"]),
        "close": float(k["c"]),
        "volume": float(k["v"]),
        "event_time": datetime.now(UTC).isoformat(),
    }


def run_producer(
    symbols: list[str] | None = None,
    bootstrap_servers: str | None = None,
    topic: str | None = None,
) -> None:
    """
    Run the Kafka producer: Binance WebSocket → Kafka topic.

    Args:
        symbols: Trading pairs to stream. Defaults to config symbols.
        bootstrap_servers: Kafka broker address.
        topic: Kafka topic name.
    """
    cfg = load_config()
    if symbols is None:
        symbols = list(cfg.symbols)
    if bootstrap_servers is None:
        bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
    if topic is None:
        topic = os.environ.get("KAFKA_TOPIC", "klines-raw")

    logger.info("Starting producer for %d symbols → %s", len(symbols), topic)

    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
    )

    running = True

    def _shutdown(*_args: Any) -> None:
        nonlocal running
        running = False
        logger.info("Shutdown signal received")

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    ws_url = _build_stream_url(symbols)
    logger.info("Connecting to %s", ws_url)

    produced_count = 0

    def on_message(_ws: Any, message: str) -> None:
        nonlocal produced_count
        data = json.loads(message)
        record = _parse_kline_event(data)
        if record:
            producer.send(topic, key=record["symbol"], value=record)
            produced_count += 1
            logger.info("Produced: %s %s", record["symbol"], record["timestamp"])

    def on_error(_ws: Any, error: Any) -> None:
        logger.error("WebSocket error: %s", error)

    def on_close(_ws: Any, status: Any, msg: Any) -> None:
        logger.info("WebSocket closed: %s %s", status, msg)

    def on_open(_ws: Any) -> None:
        logger.info("WebSocket connected, streaming %d symbols", len(symbols))

    while running:
        try:
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open,
            )
            ws.run_forever()
        except Exception as e:
            logger.error("WebSocket connection failed: %s", e)

        if running:
            logger.info("Reconnecting in 5s...")
            time.sleep(5)

    producer.flush()
    producer.close()
    logger.info("Producer stopped. Total produced: %d", produced_count)


# =============================================================================
# Order Book Depth Producer
# =============================================================================


def _build_orderbook_stream_url(symbols: list[str]) -> str:
    """Build Binance combined WebSocket stream URL for order book depth."""
    streams = [f"{s.lower()}@depth20@100ms" for s in symbols]
    return f"{BINANCE_WS_BASE}/{'/'.join(streams)}"


def _parse_orderbook_event(data: dict[str, Any], symbol: str) -> dict[str, Any] | None:
    """Parse a Binance depth WebSocket event into a structured record."""
    bids = data.get("bids", [])
    asks = data.get("asks", [])

    if not bids or not asks:
        return None

    best_bid = float(bids[0][0])
    best_ask = float(asks[0][0])
    spread = best_ask - best_bid
    mid_price = (best_bid + best_ask) / 2

    return {
        "symbol": symbol,
        "timestamp": datetime.now(UTC).isoformat(),
        "bids": [[float(p), float(q)] for p, q in bids[:20]],
        "asks": [[float(p), float(q)] for p, q in asks[:20]],
        "spread": round(spread, 8),
        "mid_price": round(mid_price, 8),
        "bid_depth": round(sum(float(q) for _, q in bids[:20]), 4),
        "ask_depth": round(sum(float(q) for _, q in asks[:20]), 4),
    }


def run_orderbook_producer(
    symbols: list[str] | None = None,
    bootstrap_servers: str | None = None,
    topic: str | None = None,
) -> None:
    """
    Run order book depth producer: Binance WebSocket → Kafka topic.

    Args:
        symbols: Trading pairs to stream. Defaults to config symbols.
        bootstrap_servers: Kafka broker address.
        topic: Kafka topic name.
    """
    cfg = load_config()
    if symbols is None:
        symbols = list(cfg.symbols)[:10]  # Limit to 10 for depth streams
    if bootstrap_servers is None:
        bootstrap_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:19092")
    if topic is None:
        topic = os.environ.get("KAFKA_ORDERBOOK_TOPIC", "orderbook-depth")

    logger.info("Starting orderbook producer for %d symbols → %s", len(symbols), topic)

    producer = KafkaProducer(
        bootstrap_servers=bootstrap_servers,
        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        key_serializer=lambda k: k.encode("utf-8"),
    )

    running = True

    def _shutdown(*_args: Any) -> None:
        nonlocal running
        running = False
        logger.info("Shutdown signal received")

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    ws_url = _build_orderbook_stream_url(symbols)
    logger.info("Connecting to %s", ws_url)

    produced_count = 0

    def on_message(_ws: Any, message: str) -> None:
        nonlocal produced_count
        data = json.loads(message)
        # Combined stream wraps in {"stream": "...", "data": {...}}
        if "stream" in data:
            stream_name = data["stream"]
            symbol = stream_name.split("@")[0].upper()
            payload = data["data"]
        else:
            symbol = data.get("s", "UNKNOWN")
            payload = data

        record = _parse_orderbook_event(payload, symbol)
        if record:
            producer.send(topic, key=record["symbol"], value=record)
            produced_count += 1
            if produced_count % 100 == 0:
                logger.info("Produced %d orderbook snapshots", produced_count)

    def on_error(_ws: Any, error: Any) -> None:
        logger.error("WebSocket error: %s", error)

    def on_close(_ws: Any, status: Any, msg: Any) -> None:
        logger.info("WebSocket closed: %s %s", status, msg)

    def on_open(_ws: Any) -> None:
        logger.info("WebSocket connected, streaming %d symbols depth", len(symbols))

    while running:
        try:
            ws = websocket.WebSocketApp(
                ws_url,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open,
            )
            ws.run_forever()
        except Exception as e:
            logger.error("WebSocket connection failed: %s", e)

        if running:
            logger.info("Reconnecting in 5s...")
            time.sleep(5)

    producer.flush()
    producer.close()
    logger.info("Orderbook producer stopped. Total produced: %d", produced_count)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )
    run_producer()
