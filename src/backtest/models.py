from dataclasses import dataclass


@dataclass
class TradeRecord:
    """Immutable-at-entry record of a simulated binary arbitrage trade."""

    timestamp: float
    market_id: str
    strategy_name: str
    capital_invested: float
    size: float
    expected_payout: float
    resolved_at: float | None = None
    realized_pnl: float | None = None

    @property
    def resolved(self) -> bool:
        return self.resolved_at is not None

    @property
    def locked_profit(self) -> float:
        return self.expected_payout - self.capital_invested

    @property
    def pnl(self) -> float:
        return self.realized_pnl if self.realized_pnl is not None else self.locked_profit

    @property
    def roi_pct(self) -> float:
        if self.capital_invested <= 0:
            return 0.0
        return (self.pnl / self.capital_invested) * 100.0
