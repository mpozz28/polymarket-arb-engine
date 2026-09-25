import pytest

from src.core.models import Market, OrderBook, OrderBookLevel, Token
from src.detectors.structural import IntraMarketArbDetector
from src.pricing.execution import PricingEngine


@pytest.fixture
def base_market():
    return Market(
        condition_id="market_001",
        question="Will it rain?",
        tokens=[
            Token(token_id="yes_1", outcome="Yes"),
            Token(token_id="no_1", outcome="No"),
        ],
        active=True,
        closed=False,
    )


def test_no_opportunity(base_market):
    books = {
        "yes_1": OrderBook(
            token_id="yes_1", timestamp=1.0, bids=[],
            asks=[OrderBookLevel(price=0.60, size=100)]
        ),
        "no_1": OrderBook(
            token_id="no_1", timestamp=1.0, bids=[],
            asks=[OrderBookLevel(price=0.45, size=100)]
        ),
    }
    detector = IntraMarketArbDetector(PricingEngine(), max_cost_threshold=0.99)
    assert detector.detect(base_market, books) == []


def test_valid_opportunity_with_slippage(base_market):
    books = {
        "yes_1": OrderBook(
            token_id="yes_1", timestamp=1.0, bids=[],
            asks=[
                OrderBookLevel(price=0.40, size=50),
                OrderBookLevel(price=0.45, size=200),
            ],
        ),
        "no_1": OrderBook(
            token_id="no_1", timestamp=1.0, bids=[],
            asks=[
                OrderBookLevel(price=0.50, size=100),
                OrderBookLevel(price=0.55, size=100),
            ],
        ),
    }
    opps = IntraMarketArbDetector(PricingEngine(), 0.99).detect(base_market, books)
    assert len(opps) == 1
    opp = opps[0]
    assert opp.max_executable_size == 100.0
    assert opp.total_capital_required == 92.5
    assert opp.expected_net_pnl == 7.5
    assert opp.expected_roi_bps == pytest.approx(810.81, rel=1e-2)


def test_fee_aware_arbitrage():
    market = Market(
        condition_id="fee_market",
        question="Fee model?",
        tokens=[Token(token_id="yes", outcome="Yes"), Token(token_id="no", outcome="No")],
        active=True,
        closed=False,
        fees_enabled=True,
        taker_fee_rate=0.05,
    )
    books = {
        "yes": OrderBook(
            token_id="yes", timestamp=1.0, bids=[],
            asks=[
                OrderBookLevel(price=0.40, size=50),
                OrderBookLevel(price=0.45, size=200),
            ],
        ),
        "no": OrderBook(
            token_id="no", timestamp=1.0, bids=[],
            asks=[
                OrderBookLevel(price=0.50, size=50),
                OrderBookLevel(price=0.55, size=200),
            ],
        ),
    }
    opps = IntraMarketArbDetector(PricingEngine(), 0.99).detect(market, books)
    assert len(opps) == 1
    assert opps[0].max_executable_size == 50.0
    assert opps[0].total_capital_required == pytest.approx(46.225)
