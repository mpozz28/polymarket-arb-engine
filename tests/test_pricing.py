import pytest
from src.core.models import OrderBook, OrderBookLevel, OrderSide
from src.pricing.execution import PricingEngine

@pytest.fixture
def mock_book():
    return OrderBook(
        token_id="test_token",
        timestamp=1600000000.0,
        bids=[
            OrderBookLevel(price=0.45, size=100.0),
            OrderBookLevel(price=0.44, size=500.0)
        ],
        asks=[
            OrderBookLevel(price=0.47, size=200.0), # L1
            OrderBookLevel(price=0.50, size=300.0), # L2
            OrderBookLevel(price=0.55, size=100.0)  # L3
        ]
    )

def test_market_order_walking(mock_book):
    engine = PricingEngine(taker_fee_rate=0.01) # 1% fee per facilitare i calcoli
    
    # Tentiamo di comprare 350 quote
    # Dovrebbe consumare:
    # 200 quote a 0.47 (L1 intero) = 94.0
    # 150 quote a 0.50 (L2 parziale) = 75.0
    # Costo totale atteso = 169.0
    # VWAP atteso = 169.0 / 350 = 0.482857...
    
    sim = engine.simulate_market_order(mock_book, OrderSide.BUY, target_size=350.0)
    
    assert sim.is_fully_filled is True
    assert sim.executed_size == 350.0
    assert sim.total_cost == pytest.approx(169.0)
    assert sim.vwap_price == pytest.approx(0.482857, rel=1e-5)
    assert sim.fees_paid == pytest.approx(1.69)
    assert sim.net_cost == pytest.approx(170.69)
    
    # Controllo Slippage in BPS (best price era 0.47, vwap è ~0.4828)
    # (0.482857 - 0.47) / 0.47 = ~0.0273 => ~273 BPS
    assert sim.slippage_bps == pytest.approx(273.55, rel=1e-2)

def test_market_order_partial_fill(mock_book):
    engine = PricingEngine()
    
    # Tentiamo di comprare 1000 quote, ma il book ne ha solo 600 totali negli asks
    sim = engine.simulate_market_order(mock_book, OrderSide.BUY, target_size=1000.0)
    
    assert sim.is_fully_filled is False
    assert sim.executed_size == 600.0
    assert sim.requested_size == 1000.0

def test_max_arb_size_calculation(mock_book):
    engine = PricingEngine(taker_fee_rate=0.00)
    
    # Usiamo lo stesso mock_book come Yes, e creiamone uno No
    no_book = OrderBook(
        token_id="test_no",
        timestamp=1600000000.0,
        bids=[],
        asks=[
            OrderBookLevel(price=0.49, size=150.0), # L1 Yes(0.47)+No(0.49) = 0.96 (Profitto 4c)
            OrderBookLevel(price=0.52, size=300.0)  # L2 Yes(0.50)+No(0.52) = 1.02 (Perdita, stop qui)
        ]
    )
    
    # Quanto posso comprare prima di andare in perdita (threshold = 0.99)?
    # Livello 1: Yes costa 0.47, No costa 0.49 (Tot = 0.96). 
    # Yes ha size 200, No ha size 150. Possiamo comprare max 150 a questo prezzo.
    # A questo punto il No book L1 è vuoto, si passa al L2 (0.52).
    # Il prossimo step combinato sarebbe: Yes L1 (0.47) + No L2 (0.52) = 0.99 (soglia). Stop.
    # Quindi la max size arbitraggiabile deve essere 150.
    
    max_size = engine.calculate_max_arb_size(mock_book, no_book, max_cost_threshold=0.99)
    assert max_size == 150.0

    