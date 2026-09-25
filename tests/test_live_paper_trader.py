import pytest

from src.core.models import Market, OrderBook, OrderBookLevel, PortfolioState, Token
from src.detectors.structural import IntraMarketArbDetector
from src.live.paper_trader import LivePaperTrader
from src.pricing.execution import PricingEngine
from src.risk.manager import RiskManager


@pytest.fixture
def trader():
    market = Market(
        condition_id="mkt_1",
        question="Event?",
        tokens=[Token(token_id="Y", outcome="Yes"), Token(token_id="N", outcome="No")],
        active=True,
        closed=False,
    )
    return LivePaperTrader(
        [market],
        [IntraMarketArbDetector(PricingEngine())],
        RiskManager(assumed_win_probability=0.99),
        PortfolioState(total_balance=10_000.0, available_balance=10_000.0, max_exposure_per_trade=0.05),
    )


@pytest.mark.asyncio
async def test_price_change_updates_existing_order_book(trader):
    trader.order_books["Y"] = OrderBook(
        token_id="Y",
        timestamp=100.0,
        bids=[OrderBookLevel(price=0.40, size=10)],
        asks=[OrderBookLevel(price=0.50, size=10), OrderBookLevel(price=0.55, size=10)],
    )
    trader.order_books["N"] = OrderBook(
        token_id="N",
        timestamp=100.0,
        bids=[],
        asks=[OrderBookLevel(price=0.50, size=10)],
    )

    await trader.process_ws_message(
        {
            "event_type": "price_change",
            "timestamp": "101000",
            "price_changes": [
                {"asset_id": "Y", "price": "0.50", "size": "0", "side": "SELL"},
                {"asset_id": "Y", "price": "0.47", "size": "12", "side": "SELL"},
            ],
        }
    )

    assert [level.price for level in trader.order_books["Y"].asks] == [0.47, 0.55]
    assert trader.order_books["Y"].asks[0].size == 12.0
    assert trader.order_books["Y"].timestamp == 101.0
