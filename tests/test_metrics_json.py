import json

from src.backtest.metrics import PerformanceMetrics
from src.backtest.models import TradeRecord


def test_profit_factor_is_none_when_there_are_no_losses():
    trade = TradeRecord(
        timestamp=1.0,
        market_id="mkt",
        strategy_name="arb",
        capital_invested=100.0,
        size=105.0,
        expected_payout=105.0,
        resolved_at=2.0,
        realized_pnl=5.0,
    )

    metrics = PerformanceMetrics.calculate_trade_metrics([trade])
    assert metrics["profit_factor"] is None
    json.dumps(metrics, allow_nan=False)
