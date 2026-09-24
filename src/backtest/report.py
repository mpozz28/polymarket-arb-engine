import json
from pathlib import Path

from src.backtest.engine import BacktestEngine


def export_backtest(engine: BacktestEngine, output_dir: str | Path) -> dict[str, str]:
    """Write a machine-readable backtest summary, trade ledger and equity curve."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    summary_path = output_path / "summary.json"
    trades_path = output_path / "trades.csv"
    equity_path = output_path / "equity_curve.csv"

    summary_path.write_text(
        json.dumps(engine.summary(), indent=2, allow_nan=False),
        encoding="utf-8",
    )

    trade_lines = [
        (
            "timestamp,market_id,strategy_name,capital_invested,size,expected_payout,"
            "resolved_at,realized_pnl,roi_pct"
        )
    ]
    for trade in engine.trade_history:
        values = [
            trade.timestamp,
            trade.market_id,
            trade.strategy_name,
            trade.capital_invested,
            trade.size,
            trade.expected_payout,
            "" if trade.resolved_at is None else trade.resolved_at,
            "" if trade.realized_pnl is None else trade.realized_pnl,
            trade.roi_pct,
        ]
        trade_lines.append(",".join(str(value) for value in values))
    trades_path.write_text("\n".join(trade_lines) + "\n", encoding="utf-8")

    equity_lines = ["timestamp,total_balance"]
    equity_lines.extend(
        f"{timestamp},{balance}" for timestamp, balance in engine.equity_curve
    )
    equity_path.write_text("\n".join(equity_lines) + "\n", encoding="utf-8")

    return {
        "summary": str(summary_path),
        "trades": str(trades_path),
        "equity_curve": str(equity_path),
    }
