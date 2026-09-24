import pandas as pd
import pytest

from src.backtest.engine import BacktestEngine
from src.backtest.metrics import PerformanceMetrics
from src.core.models import Market, OrderBook, OrderBookLevel, Token
from src.detectors.structural import IntraMarketArbDetector
from src.pricing.execution import PricingEngine
from src.risk.manager import RiskManager


def mock_data_generator():
    """Minimal event stream covering entry, no-entry, and settlement."""
    market = Market(
        condition_id="mkt_1",
        question="Event?",
        tokens=[Token(token_id="Y", outcome="Yes"), Token(token_id="N", outcome="No")],
        active=True,
        closed=False,
    )

    books_t1 = {
        "Y": OrderBook(
            token_id="Y",
            timestamp=100.0,
            bids=[],
            asks=[OrderBookLevel(price=0.40, size=1000)],
        ),
        "N": OrderBook(
            token_id="N",
            timestamp=100.0,
            bids=[],
            asks=[OrderBookLevel(price=0.50, size=1000)],
        ),
    }
    yield 100.0, market, books_t1

    books_t2 = {
        "Y": OrderBook(
            token_id="Y",
            timestamp=200.0,
            bids=[],
            asks=[OrderBookLevel(price=0.60, size=1000)],
        ),
        "N": OrderBook(
            token_id="N",
            timestamp=200.0,
            bids=[],
            asks=[OrderBookLevel(price=0.45, size=1000)],
        ),
    }
    yield 200.0, market, books_t2

    closed_market = market.model_copy(update={"closed": True, "active": False})
    yield 300.0, closed_market, books_t2


def make_engine() -> BacktestEngine:
    detector = IntraMarketArbDetector(PricingEngine(taker_fee_rate=0.0), max_cost_threshold=0.99)
    return BacktestEngine(
        initial_capital=10_000.0,
        detectors=[detector],
        risk_manager=RiskManager(assumed_win_probability=0.99),
    )


def test_full_backtest_loop():
    backtester = make_engine()
    backtester.run(mock_data_generator())

    assert len(backtester.trade_history) == 1
    trade = backtester.trade_history[0]
    assert trade.capital_invested == 500.0

    expected_shares = 500.0 / 0.90
    assert trade.expected_payout == pytest.approx(expected_shares)
    assert trade.resolved
    assert trade.realized_pnl == pytest.approx(expected_shares - 500.0)
    assert backtester.portfolio.total_balance == pytest.approx(10_000.0 + trade.realized_pnl)
    assert backtester.portfolio.available_balance == pytest.approx(
        backtester.portfolio.total_balance
    )


def test_no_duplicate_entry_while_position_is_open():
    market = Market(
        condition_id="mkt_1",
        question="Event?",
        tokens=[Token(token_id="Y", outcome="Yes"), Token(token_id="N", outcome="No")],
        active=True,
        closed=False,
    )
    books = {
        "Y": OrderBook(
            token_id="Y", timestamp=100.0, bids=[], asks=[OrderBookLevel(price=0.40, size=1000)]
        ),
        "N": OrderBook(
            token_id="N", timestamp=100.0, bids=[], asks=[OrderBookLevel(price=0.50, size=1000)]
        ),
    }

    def feed():
        yield 100.0, market, books
        yield 101.0, market, books
        yield 102.0, market.model_copy(update={"closed": True, "active": False}), books

    backtester = make_engine()
    backtester.run(feed())

    assert len(backtester.trade_history) == 1
    assert backtester.trade_history[0].resolved


def test_trade_and_equity_metrics():
    backtester = make_engine()
    backtester.run(mock_data_generator())

    metrics = backtester.summary()
    assert metrics["total_trades"] == 1
    assert metrics["resolved_trades"] == 1
    assert metrics["total_pnl"] > 0
    assert metrics["win_rate_pct"] == 100.0
    assert metrics["profit_factor"] is None
    assert metrics["total_return_pct"] == pytest.approx(0.5555555556)
    assert metrics["max_drawdown_pct"] == 0.0
    assert metrics["initial_capital"] == 10_000.0
    assert metrics["final_total_balance"] == pytest.approx(10_055.555555555555)
    assert metrics["final_available_balance"] == pytest.approx(10_055.555555555555)


def test_performance_metrics():
    returns = [0.002] * 19 + [-0.01]
    series = pd.Series(returns)

    metrics = PerformanceMetrics.calculate_metrics(series, risk_free_rate=0.0)

    assert metrics["win_rate_pct"] == 95.0
    assert metrics["max_drawdown_pct"] < 0
    assert metrics["sharpe_ratio"] > 0
