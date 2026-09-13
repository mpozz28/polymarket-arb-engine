import pytest
from src.data.polymarket_client import PolymarketDataClient
from src.core.models import Market, OrderBook

@pytest.fixture
def client():
    return PolymarketDataClient(
        gamma_url="https://gamma-api.polymarket.com",
        clob_url="https://clob.polymarket.com"
    )

@pytest.mark.asyncio
async def test_get_active_markets(client, httpx_mock):
    mock_gamma_response = [{
        "conditionId": "0x123...",
        "question": "Will rates be cut?",
        "active": True,
        "closed": False,
        "outcomes": ["Yes", "No"],
        "tokens": [{"token_id": "111"}, {"token_id": "222"}]
    }]
    
    httpx_mock.add_response(url="https://gamma-api.polymarket.com/markets?closed=false&active=true&limit=10&offset=0", json=mock_gamma_response)
    
    markets = await client.get_active_markets(limit=10)
    
    assert len(markets) == 1
    assert markets[0].question == "Will rates be cut?"
    assert len(markets[0].tokens) == 2
    assert markets[0].tokens[0].token_id == "111"

@pytest.mark.asyncio
async def test_get_order_book(client, httpx_mock):
    mock_clob_response = {
        "bids": [{"price": "0.45", "size": "1000.5"}],
        "asks": [{"price": "0.47", "size": "500.0"}]
    }
    
    httpx_mock.add_response(url="https://clob.polymarket.com/book?token_id=111", json=mock_clob_response)
    
    book = await client.get_order_book(token_id="111")
    
    assert book is not None
    assert book.token_id == "111"
    assert book.best_bid == 0.45
    assert book.best_ask == 0.47
    assert book.asks[0].size == 500.0

@pytest.mark.asyncio
async def test_client_close(client):
    await client.close()
    assert client.client.is_closed