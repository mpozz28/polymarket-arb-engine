from enum import Enum

from pydantic import BaseModel, Field


class Token(BaseModel):
    token_id: str
    outcome: str
    price: float = 0.0


class Market(BaseModel):
    condition_id: str
    question: str
    tokens: list[Token]
    active: bool
    closed: bool
    market_type: str = Field(default="binary", description="binary or categorical")
    fees_enabled: bool = False
    taker_fee_rate: float = 0.0


class OrderBookLevel(BaseModel):
    price: float
    size: float


class OrderBook(BaseModel):
    token_id: str
    timestamp: float
    bids: list[OrderBookLevel]
    asks: list[OrderBookLevel]

    @property
    def best_bid(self) -> float:
        return max((level.price for level in self.bids), default=0.0)

    @property
    def best_ask(self) -> float:
        return min((level.price for level in self.asks), default=1.0)


class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class ExecutionSimulation(BaseModel):
    side: OrderSide
    requested_size: float
    executed_size: float
    vwap_price: float
    total_cost: float
    fees_paid: float
    slippage_bps: float
    is_fully_filled: bool

    @property
    def net_cost(self) -> float:
        if self.side == OrderSide.BUY:
            return self.total_cost + self.fees_paid
        return self.total_cost - self.fees_paid


class ArbLeg(BaseModel):
    token_id: str
    side: OrderSide
    size: float
    expected_vwap: float


class Opportunity(BaseModel):
    market_id: str
    strategy_name: str
    timestamp: float
    legs: list[ArbLeg]
    max_executable_size: float
    total_capital_required: float
    expected_net_pnl: float
    expected_roi_bps: float

    @property
    def is_profitable(self) -> bool:
        return self.expected_net_pnl > 0


class PortfolioState(BaseModel):
    total_balance: float
    available_balance: float
    max_exposure_per_trade: float
    fractional_kelly_multiplier: float = 0.5


class ApprovedTrade(BaseModel):
    opportunity: Opportunity
    approved_capital: float
    approved_size: float
    kelly_fraction_suggested: float
    reason: str
