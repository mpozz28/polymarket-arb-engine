from unittest.mock import AsyncMock

import pytest

from src.core.models import OrderBook
from src.data.polymarket_client import PolymarketDataClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


@pytest.fixture
def client():
    return PolymarketDataClient(
        gamma_url="https://gamma-api.polymarket.com",
        clob_url="https://clob.polymarket.com",
    )


@pytest.mark.asyncio
async def test_get_active_markets_parses_current_fields(client):
    client.client.get = AsyncMock(
        return_value=FakeResponse(
            [
                {
                    "conditionId": "0x123",
                    "question": "Will rates be cut?",
                    "active": True,
                    "closed": False,
                    "outcomes": ["Yes", "No"],
                    "clobTokenIds": ["111", "222"],
                    "feesEnabled": True,
                    "feeSchedule": {"rate": 0.05},
                }
            ]
        )
    )

    markets = await client.get_active_markets(limit=10)

    assert len(markets) == 1
    assert markets[0].question == "Will rates be cut?"
    assert [token.token_id for token in markets[0].tokens] == ["111", "222"]
    assert markets[0].fees_enabled is True
    assert markets[0].taker_fee_rate == 0.05


@pytest.mark.asyncio
async def test_get_order_book_parses_snapshot(client):
    client.client.get = AsyncMock(
        return_value=FakeResponse(
            {
                "bids": [{"price": "0.45", "size": "1000.5"}],
                "asks": [{"price": "0.47", "size": "500.0"}],
            }
        )
    )

    book = await client.get_order_book(token_id="111")

    assert isinstance(book, OrderBook)
    assert book.best_bid == 0.45
    assert book.best_ask == 0.47
    assert book.asks[0].size == 500.0


@pytest.mark.asyncio
async def test_client_close(client):
    client.client.close = AsyncMock()
    await client.close()
    client.client.close.assert_awaited_once()
