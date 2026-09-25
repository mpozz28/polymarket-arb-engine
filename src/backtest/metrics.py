from collections.abc import Iterable, Sequence
from typing import Any

import numpy as np
import pandas as pd

from src.backtest.models import TradeRecord


class PerformanceMetrics:
    @staticmethod
    def calculate_metrics(
        daily_returns: pd.Series, risk_free_rate: float = 0.04
    ) -> dict[str, Any]:
        """Calculate standard metrics from a series of daily returns."""
        if daily_returns.empty or daily_returns.std() == 0:
            return {"sharpe_ratio": 0.0, "max_drawdown": 0.0, "win_rate": 0.0}

        trading_days = 365
        daily_rf = (1 + risk_free_rate) ** (1 / trading_days) - 1
        excess_returns = daily_returns - daily_rf

        sharpe = np.sqrt(trading_days) * (excess_returns.mean() / daily_returns.std())

        downside_returns = daily_returns[daily_returns < 0]
        downside_std = downside_returns.std() if not downside_returns.empty else 1e-9
        sortino = np.sqrt(trading_days) * (excess_returns.mean() / downside_std)

        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.cummax()
        drawdowns = (cumulative - running_max) / running_max
        max_dd = drawdowns.min()

        win_rate = (
            len(daily_returns[daily_returns > 0]) / len(daily_returns)
            if len(daily_returns) > 0
            else 0
        )

        return {
            "total_return_pct": (cumulative.iloc[-1] - 1) * 100
            if not cumulative.empty
            else 0.0,
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "max_drawdown_pct": float(max_dd) * 100,
            "win_rate_pct": float(win_rate) * 100,
        }

    @staticmethod
    def calculate_trade_metrics(trades: Sequence[TradeRecord]) -> dict[str, Any]:
        resolved = [trade for trade in trades if trade.resolved]
        pnls = [trade.pnl for trade in resolved]
        invested = sum(trade.capital_invested for trade in resolved)
        total_pnl = sum(pnls)
        winners = [pnl for pnl in pnls if pnl > 0]
        losers = [pnl for pnl in pnls if pnl < 0]
        gross_profit = sum(winners)
        gross_loss = abs(sum(losers))

        return {
            "total_trades": len(trades),
            "resolved_trades": len(resolved),
            "open_trades": len(trades) - len(resolved),
            "total_pnl": float(total_pnl),
            "total_capital_invested": float(invested),
            "return_on_invested_capital_pct": float(total_pnl / invested * 100)
            if invested > 0
            else 0.0,
            "win_rate_pct": float(len(winners) / len(resolved) * 100)
            if resolved
            else 0.0,
            "average_trade_pnl": float(total_pnl / len(resolved)) if resolved else 0.0,
            "gross_profit": float(gross_profit),
            "gross_loss": float(gross_loss),
            # Undefined when there are no losing trades; JSON output uses null.
            "profit_factor": float(gross_profit / gross_loss)
            if gross_loss > 0
            else None,
            "average_roi_pct": float(
                sum(trade.roi_pct for trade in resolved) / len(resolved)
            )
            if resolved
            else 0.0,
        }

    @staticmethod
    def calculate_equity_metrics(
        equity_curve: Iterable[tuple[float, float]],
    ) -> dict[str, float]:
        points = list(equity_curve)
        if not points:
            return {"total_return_pct": 0.0, "max_drawdown_pct": 0.0}

        values = np.asarray([value for _, value in points], dtype=float)
        running_max = np.maximum.accumulate(values)
        drawdowns = np.divide(
            values - running_max,
            running_max,
            out=np.zeros_like(values),
            where=running_max != 0,
        )

        initial = values[0]
        final = values[-1]
        return {
            "total_return_pct": float((final / initial - 1.0) * 100) if initial else 0.0,
            "max_drawdown_pct": float(drawdowns.min() * 100),
        }
