from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class Token(BaseModel):
    token_id: str
    outcome: str
    price: float = 0.0

class Market(BaseModel):
    condition_id: str
    question: str
    tokens: List[Token]
    active: bool
    closed: bool
    # Utile per calcolare se la somma di N token mutualmente esclusivi fa 1.00$
    market_type: str = Field(default="binary", description="Può essere 'binary' o 'categorical'")

class OrderBookLevel(BaseModel):
    price: float
    size: float

class OrderBook(BaseModel):
    token_id: str
    timestamp: float
    bids: List[OrderBookLevel]
    asks: List[OrderBookLevel]

    @property
    def best_bid(self) -> float:
        return self.bids[0].price if self.bids else 0.0

    @property
    def best_ask(self) -> float:
        return self.asks[0].price if self.asks else 1.0

class OrderSide(str, Enum):
    BUY = "BUY"
    SELL = "SELL"

class ExecutionSimulation(BaseModel):
    side: OrderSide
    requested_size: float
    executed_size: float
    vwap_price: float        # Volume-Weighted Average Price
    total_cost: float        # Costo totale (escluse fee)
    fees_paid: float         # Fee in dollari (o pUSD)
    slippage_bps: float      # Slippage in basis points (1 bp = 0.01%) rispetto al best price
    is_fully_filled: bool
    
    @property
    def net_cost(self) -> float:
        """Costo totale inclusivo di fee (per i BUY) o ricavo netto (per i SELL)"""
        if self.side == OrderSide.BUY:
            return self.total_cost + self.fees_paid
        else:
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
    legs: List[ArbLeg]
    max_executable_size: float  # Quante "quote" del trade possiamo eseguire
    total_capital_required: float # Capitale stimato per eseguire l'intera size
    expected_net_pnl: float     # Profitto netto atteso (in pUSD/USD)
    expected_roi_bps: float     # Ritorno sull'investimento in Basis Points

    @property
    def is_profitable(self) -> bool:
        return self.expected_net_pnl > 0

class PortfolioState(BaseModel):
    total_balance: float            # Capitale totale (es. 10000 pUSD)
    available_balance: float        # Capitale non bloccato in ordini attivi
    max_exposure_per_trade: float   # Percentuale massima allocabile su un singolo trade (es. 0.05 per 5%)
    fractional_kelly_multiplier: float = 0.5 # Es. 0.5 = Half-Kelly (più conservativo)

class ApprovedTrade(BaseModel):
    opportunity: Opportunity
    approved_capital: float         # Quanto capitale investire (<= opportunity.total_capital_required)
    approved_size: float            # Quante quote comprare
    kelly_fraction_suggested: float # Frazione suggerita matematicamente
    reason: str                     # Es. "Capped by max exposure", "Capped by order book"