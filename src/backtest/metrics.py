import numpy as np
import pandas as pd
from typing import List, Dict, Any

class PerformanceMetrics:
    @staticmethod
    def calculate_metrics(daily_returns: pd.Series, risk_free_rate: float = 0.04) -> Dict[str, Any]:
        """
        Calcola le metriche di performance su una serie storica di rendimenti giornalieri.
        risk_free_rate: ~4% annualizzato (rendimento dei bond USA a breve termine o yield USDC/pUSD).
        """
        if daily_returns.empty or daily_returns.std() == 0:
            return {"sharpe_ratio": 0.0, "max_drawdown": 0.0, "win_rate": 0.0}

        # Assumiamo 365 giorni operativi per le crypto/prediction markets
        trading_days = 365 
        daily_rf = (1 + risk_free_rate) ** (1/trading_days) - 1

        excess_returns = daily_returns - daily_rf
        
        # Sharpe Ratio
        sharpe = np.sqrt(trading_days) * (excess_returns.mean() / daily_returns.std())
        
        # Sortino Ratio (penalizza solo la volatilità negativa)
        downside_returns = daily_returns[daily_returns < 0]
        downside_std = downside_returns.std() if not downside_returns.empty else 1e-9
        sortino = np.sqrt(trading_days) * (excess_returns.mean() / downside_std)

        # Max Drawdown
        cumulative = (1 + daily_returns).cumprod()
        running_max = cumulative.cummax()
        drawdowns = (cumulative - running_max) / running_max
        max_dd = drawdowns.min()

        # Win rate (giorni in profitto)
        win_rate = len(daily_returns[daily_returns > 0]) / len(daily_returns) if len(daily_returns) > 0 else 0

        return {
            "total_return_pct": (cumulative.iloc[-1] - 1) * 100 if not cumulative.empty else 0.0,
            "sharpe_ratio": float(sharpe),
            "sortino_ratio": float(sortino),
            "max_drawdown_pct": float(max_dd) * 100,
            "win_rate_pct": float(win_rate) * 100
        }