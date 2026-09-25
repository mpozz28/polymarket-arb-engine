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
            OrderBookLevel(price=0.44, size=500.0),
        ],
        asks=[
            OrderBookLevel(price=0.47, size=200.0),
            OrderBookLevel(price=0.50, size=300.0),
            OrderBookLevel(price=0.55, size=100.0),
        ],
    )


def test_market_order_walking(mock_book):
    engine = PricingEngine()
    sim = engine.simulate_market_order(mock_book, OrderSide.BUY, target_size=350.0)

    assert sim.is_fully_filled is True
    assert sim.executed_size == 350.0
    assert sim.total_cost == pytest.approx(169.0)
    assert sim.vwap_price == pytest.approx(169.0 / 350.0)
    assert sim.fees_paid == 0.0
    assert sim.net_cost == pytest.approx(169.0)
    assert sim.slippage_bps == pytest.approx(273.55, rel=1e-2)


def test_fee_calculation_is_price_sensitive(mock_book):
    engine = PricingEngine()
    sim = engine.simulate_market_order(
        mock_book,
        OrderSide.BUY,
        target_size=350.0,
        fee_rate=0.01,
    )

    expected_fee = (
        PricingEngine.taker_fee_usd(200.0, 0.47, 0.01)
        + PricingEngine.taker_fee_usd(150.0, 0.50, 0.01)
    )
    assert sim.fees_paid == pytest.approx(expected_fee)
    assert sim.net_cost == pytest.approx(169.0 + expected_fee)


def test_market_order_partial_fill(mock_book):
    sim = PricingEngine().simulate_market_order(mock_book, OrderSide.BUY, target_size=1000.0)
    assert sim.is_fully_filled is False
    assert sim.executed_size == 600.0
    assert sim.requested_size == 1000.0


def test_max_arb_size_calculation(mock_book):
    no_book = OrderBook(
        token_id="test_no",
        timestamp=1600000000.0,
        bids=[],
        asks=[
            OrderBookLevel(price=0.49, size=150.0),
            OrderBookLevel(price=0.52, size=300.0),
        ],
    )
    assert PricingEngine().calculate_max_arb_size(
        mock_book, no_book, max_cost_threshold=0.99
    ) == 150.0
