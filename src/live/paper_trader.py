import logging
import math
import time
from typing import Any

from src.core.models import Market, OrderBook, OrderBookLevel, PortfolioState
from src.detectors.base import BaseDetector
from src.risk.manager import RiskManager

logger = logging.getLogger(__name__)


def _timestamp_seconds(value: object, reference_seconds: float | None = None) -> float:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return 0.0

    # Real Unix timestamps in milliseconds are ~1e12.
    if timestamp >= 100_000_000_000:
        return timestamp / 1000.0

    # For synthetic/test timestamps, infer the unit from the previous
    # order-book timestamp when available.
    if reference_seconds is not None and reference_seconds > 0:
        seconds_candidate = timestamp
        milliseconds_candidate = timestamp / 1000.0

        seconds_distance = abs(seconds_candidate - reference_seconds)
        milliseconds_distance = abs(milliseconds_candidate - reference_seconds)

        if milliseconds_distance < seconds_distance:
            return milliseconds_candidate

    return timestamp


class LivePaperTrader:
    def __init__(
        self,
        markets: list[Market],
        detectors: list[BaseDetector],
        risk_manager: RiskManager,
        portfolio: PortfolioState,
    ):
        self.detectors = detectors
        self.risk_manager = risk_manager
        self.portfolio = portfolio
        self.markets_by_token: dict[str, Market] = {
            token.token_id: market
            for market in markets
            for token in market.tokens
        }
        self.order_books: dict[str, OrderBook] = {}
        self.last_alert_time: dict[str, float] = {}

    async def process_ws_message(self, data: Any) -> None:
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    await self._parse_single_message(item)
        elif isinstance(data, dict):
            await self._parse_single_message(data)

    async def _parse_single_message(self, data: dict) -> None:
        start_time = time.perf_counter()
        event_type = str(data.get("event_type", data.get("type", ""))).lower()

        if event_type == "price_change":
            self._handle_price_change(data)
        elif event_type == "book" or "bids" in data or "asks" in data:
            self._handle_book_snapshot(data)

        processing_time_ms = (time.perf_counter() - start_time) * 1000.0
        if processing_time_ms > 1.0:
            logger.info("Market-data processing latency: %.3f ms", processing_time_ms)

    def _handle_book_snapshot(self, data: dict) -> None:
        token_id = str(data.get("asset_id", data.get("token_id", "")))
        if not token_id or token_id not in self.markets_by_token:
            return

        self.order_books[token_id] = OrderBook(
            token_id=token_id,
            timestamp=_timestamp_seconds(data.get("timestamp")),
            bids=self._sort_levels(data.get("bids", data.get("buys", [])), reverse=True),
            asks=self._sort_levels(data.get("asks", data.get("sells", [])), reverse=False),
        )
        self._evaluate_if_market_ready(self.markets_by_token[token_id])

    def _handle_price_change(self, data: dict) -> None:
        changes = data.get("price_changes", data.get("changes", []))
        if not isinstance(changes, list):
            return

        affected_markets = []

        for change in changes:
            if not isinstance(change, dict):
                continue

            token_id = str(change.get("asset_id", change.get("token_id", "")))
            market = self.markets_by_token.get(token_id)
            book = self.order_books.get(token_id)

            if market is None or book is None:
                continue

            timestamp = _timestamp_seconds(
                data.get("timestamp"),
                reference_seconds=book.timestamp,
            )

            try:
                price = float(change["price"])
                size = float(change["size"])
            except (KeyError, TypeError, ValueError):
                continue

            side = str(change.get("side", "")).upper()
            if side not in {"BUY", "SELL"}:
                continue

            levels = book.bids if side == "BUY" else book.asks
            levels[:] = [
                level for level in levels
                if not math.isclose(level.price, price, abs_tol=1e-12)
            ]
            if size > 0:
                levels.append(OrderBookLevel(price=price, size=size))

            levels.sort(key=lambda level: level.price, reverse=side == "BUY")
            book.timestamp = timestamp if timestamp else book.timestamp
            if market not in affected_markets:
                affected_markets.append(market)

        for market in affected_markets:
            self._evaluate_if_market_ready(market)

    @staticmethod
    def _sort_levels(raw_levels: Any, reverse: bool) -> list[OrderBookLevel]:
        if not isinstance(raw_levels, list):
            return []

        levels: list[OrderBookLevel] = []
        for raw in raw_levels:
            if not isinstance(raw, dict):
                continue
            try:
                levels.append(OrderBookLevel(price=float(raw["price"]), size=float(raw["size"])))
            except (KeyError, TypeError, ValueError):
                continue
        return sorted(levels, key=lambda level: level.price, reverse=reverse)

    def _evaluate_if_market_ready(self, market: Market) -> None:
        if all(token.token_id in self.order_books for token in market.tokens):
            self._evaluate_market(market)

    def _evaluate_market(self, market: Market) -> None:
        if len(market.tokens) == 2:
            first = market.tokens[0].token_id
            second = market.tokens[1].token_id
            book1 = self.order_books.get(first)
            book2 = self.order_books.get(second)
            if book1 and book2 and book1.asks and book2.asks:
                spread_sum = book1.best_ask + book2.best_ask
                if spread_sum < 1.05:
                    logger.info(
                        "[LIVE SPREAD] %s | top-of-book sum: $%.3f",
                        market.question[:80],
                        spread_sum,
                    )

        for detector in self.detectors:
            for opportunity in detector.detect(market, self.order_books):
                trade = self.risk_manager.evaluate_opportunity(opportunity, self.portfolio)
                if trade.approved_capital > 0:
                    self._execute_paper_trade(trade, market)

    def _execute_paper_trade(self, trade, market: Market) -> None:
        current_time = time.time()
        if current_time - self.last_alert_time.get(market.condition_id, 0.0) < 10.0:
            return

        self.last_alert_time[market.condition_id] = current_time
        logger.info("%s", "=" * 60)
        logger.info("PAPER ARBITRAGE: %s", market.question)
        logger.info(
            "Average executable cost/share: $%.4f | max size: %.2f",
            trade.opportunity.total_capital_required / trade.opportunity.max_executable_size,
            trade.opportunity.max_executable_size,
        )
        logger.info("Capital allocated: $%.2f (%s)", trade.approved_capital, trade.reason)
        logger.info(
            "Expected net PnL: $%.2f | ROI: %.2f%%",
            trade.opportunity.expected_net_pnl,
            trade.opportunity.expected_roi_bps / 100.0,
        )
        logger.info("%s", "=" * 60)
