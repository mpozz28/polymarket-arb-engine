from abc import ABC, abstractmethod
from typing import List, Dict
from src.core.models import Market, OrderBook, Opportunity
from src.pricing.execution import PricingEngine

class BaseDetector(ABC):
    def __init__(self, pricing_engine: PricingEngine):
        self.pricing_engine = pricing_engine
        self.strategy_name = self.__class__.__name__

    @abstractmethod
    def detect(self, market: Market, order_books: Dict[str, OrderBook]) -> List[Opportunity]:
        """
        Analizza un mercato e i suoi Order Book correnti.
        order_books è un dizionario: {token_id: OrderBook}
        Ritorna una lista di opportunità trovate (vuota se nessuna).
        """
        pass