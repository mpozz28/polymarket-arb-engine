from collections.abc import Iterator

from src.backtest.models import TradeRecord
from src.core.models import ApprovedTrade, Market, OrderBook, PortfolioState
from src.detectors.base import BaseDetector
from src.risk.manager import RiskManager


class BacktestEngine:
    """Event-driven backtest engine for binary structural arbitrage."""

    def __init__(
        self,
        initial_capital: float,
        detectors: list[BaseDetector],
        risk_manager: RiskManager,
        max_exposure_per_trade: float = 0.05,
        fractional_kelly_multiplier: float = 0.5,
    ):
        if initial_capital <= 0:
            raise ValueError("initial_capital must be greater than zero")
        if not 0.0 < max_exposure_per_trade <= 1.0:
            raise ValueError("max_exposure_per_trade must be in (0, 1]")
        if not 0.0 <= fractional_kelly_multiplier <= 1.0:
            raise ValueError("fractional_kelly_multiplier must be in [0, 1]")

        self.portfolio = PortfolioState(
            total_balance=initial_capital,
            available_balance=initial_capital,
            max_exposure_per_trade=max_exposure_per_trade,
            fractional_kelly_multiplier=fractional_kelly_multiplier,
        )
        self.detectors = detectors
        self.risk_manager = risk_manager
        self.active_trades: list[TradeRecord] = []
        self.trade_history: list[TradeRecord] = []
        self.equity_curve: list[tuple[float, float]] = [(0.0, initial_capital)]

    def resolve_market(self, market_id: str, timestamp: float) -> None:
        """Settle all active trades for a market at binary payout = $1/share."""
        still_active: list[TradeRecord] = []

        for trade in self.active_trades:
            if trade.market_id != market_id or trade.resolved:
                still_active.append(trade)
                continue

            trade.resolved_at = timestamp
            trade.realized_pnl = trade.expected_payout - trade.capital_invested
            self.portfolio.total_balance += trade.realized_pnl
            self.portfolio.available_balance += trade.expected_payout

        self.active_trades = still_active

    def run(self, data_feed: Iterator[tuple[float, Market, dict[str, OrderBook]]]) -> None:
        """Replay an ordered stream of market snapshots without lookahead."""
        for current_time, market, order_books in data_feed:
            if market.closed:
                self.resolve_market(market.condition_id, current_time)
                self._append_equity_point(current_time)
                continue

            evaluated: set[tuple[str, str]] = set()
            for detector in self.detectors:
                key = (market.condition_id, detector.strategy_name)
                if key in evaluated:
                    continue
                evaluated.add(key)

                for opportunity in detector.detect(market, order_books):
                    approved_trade = self.risk_manager.evaluate_opportunity(
                        opportunity, self.portfolio
                    )
                    if approved_trade.approved_capital > 0:
                        self.execute_trade(current_time, approved_trade)

            self._append_equity_point(current_time)

    def execute_trade(self, timestamp: float, trade: ApprovedTrade) -> bool:
        """Lock capital for one active position per market."""
        if trade.approved_capital <= 0 or trade.approved_size <= 0:
            return False

        if any(
            active.market_id == trade.opportunity.market_id and not active.resolved
            for active in self.active_trades
        ):
            return False

        self.portfolio.available_balance -= trade.approved_capital

        record = TradeRecord(
            timestamp=timestamp,
            market_id=trade.opportunity.market_id,
            strategy_name=trade.opportunity.strategy_name,
            capital_invested=trade.approved_capital,
            size=trade.approved_size,
            expected_payout=trade.approved_size,
        )
        self.active_trades.append(record)
        self.trade_history.append(record)
        return True

    def summary(self) -> dict:
        """Return trade-level and portfolio-level summary metrics."""
        from src.backtest.metrics import PerformanceMetrics

        metrics = PerformanceMetrics.calculate_trade_metrics(self.trade_history)
        metrics.update(PerformanceMetrics.calculate_equity_metrics(self.equity_curve))
        metrics["initial_capital"] = self.equity_curve[0][1] if self.equity_curve else 0.0
        metrics["final_total_balance"] = self.portfolio.total_balance
        metrics["final_available_balance"] = self.portfolio.available_balance
        return metrics

    def _append_equity_point(self, timestamp: float) -> None:
        if self.equity_curve and self.equity_curve[-1][0] == timestamp:
            self.equity_curve[-1] = (timestamp, self.portfolio.total_balance)
        else:
            self.equity_curve.append((timestamp, self.portfolio.total_balance))
