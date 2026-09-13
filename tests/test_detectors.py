import pytest
from src.core.models import Market, Token, OrderBook, OrderBookLevel
from src.pricing.execution import PricingEngine
from src.detectors.structural import IntraMarketArbDetector

@pytest.fixture
def base_market():
    return Market(
        condition_id="market_001",
        question="Will it rain?",
        tokens=[Token(token_id="yes_1", outcome="Yes"), Token(token_id="no_1", outcome="No")],
        active=True,
        closed=False
    )

def test_no_opportunity(base_market):
    # Prezzo Yes = 0.60, Prezzo No = 0.45. Totale 1.05 -> Nessun arbitraggio
    books = {
        "yes_1": OrderBook(token_id="yes_1", timestamp=1.0, bids=[], asks=[OrderBookLevel(price=0.60, size=100)]),
        "no_1": OrderBook(token_id="no_1", timestamp=1.0, bids=[], asks=[OrderBookLevel(price=0.45, size=100)])
    }
    
    engine = PricingEngine()
    detector = IntraMarketArbDetector(engine, max_cost_threshold=0.99)
    opps = detector.detect(base_market, books)
    
    assert len(opps) == 0

def test_valid_opportunity_with_slippage(base_market):
    # L1: Yes=0.40, No=0.50 (Tot 0.90 -> Arbitraggio profittevole) - Max Size: 50
    # L2: Yes=0.45, No=0.55 (Tot 1.00 -> NON profittevole)
    books = {
        "yes_1": OrderBook(token_id="yes_1", timestamp=1.0, bids=[], asks=[
            OrderBookLevel(price=0.40, size=50),
            OrderBookLevel(price=0.45, size=200)
        ]),
        "no_1": OrderBook(token_id="no_1", timestamp=1.0, bids=[], asks=[
            OrderBookLevel(price=0.50, size=100),
            OrderBookLevel(price=0.55, size=100)
        ])
    }
    
    engine = PricingEngine(taker_fee_rate=0.0)
    detector = IntraMarketArbDetector(engine, max_cost_threshold=0.99)
    opps = detector.detect(base_market, books)
    
    assert len(opps) == 1
    opp = opps[0]
        
    # L'algoritmo calcola giustamente 100 quote eseguibili incrociando i livelli
    assert opp.max_executable_size == 100.0
    # Costo totale: 
    # Yes: (50 * 0.40) + (50 * 0.45) = 20.0 + 22.5 = 42.5
    # No: (100 * 0.50) = 50.0
    # Totale = 92.5
    assert opp.total_capital_required == 92.5
    
    # Payout atteso = 100.0. Net PnL = 100.0 - 92.5 = 7.5
    assert opp.expected_net_pnl == 7.5
    
    # ROI = 7.5 / 92.5 = 8.108% = 810.81 BPS
    assert opp.expected_roi_bps == pytest.approx(810.81, rel=1e-2)
    