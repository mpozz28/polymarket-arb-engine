from curl_cffi.requests import AsyncSession
import asyncio
import time
from typing import List, Dict, Any, Optional
from src.core.models import Market, Token, OrderBook, OrderBookLevel
import logging

logger = logging.getLogger(__name__)

class PolymarketDataClient:
    """
    Client Asincrono Read-Only per l'ingestion dei mercati (Gamma API) e Order Book (CLOB API).
    """
    
    def __init__(self, gamma_url: str, clob_url: str, concurrency_limit: int = 50):
        self.gamma_url = gamma_url.rstrip('/')
        self.clob_url = clob_url.rstrip('/')
        self.client = AsyncSession(impersonate="chrome110", timeout=15.0, verify=False)
        self.semaphore = asyncio.Semaphore(concurrency_limit)
        
    async def get_active_markets(self, limit: int = 50, offset: int = 0) -> List[Market]:
        url = f"{self.gamma_url}/markets"
        params = {"limit": limit, "offset": offset}
        
        async with self.semaphore:
            try:
                response = await self.client.get(url, params=params)
                data = response.json()
            except Exception as e:
                logger.error(f"Errore Gamma API: {e}")
                return []
        
        if isinstance(data, dict):
            data = data.get("data", data.get("markets", []))
            
        if not isinstance(data, list):
            logger.error("Formato API irriconoscibile.")
            return []
            
        parsed_markets = []
        for m in data:
            if not isinstance(m, dict): continue
            
            # Polymarket a volte usa stringhe "true"/"false" invece di booleani
            is_closed = m.get("closed", False)
            if str(is_closed).lower() == "true":
                continue
                
            try:
                outcomes = m.get("outcomes", [])
                if isinstance(outcomes, str):
                    import json
                    outcomes = json.loads(outcomes)
                
                # Il trucco è qui: cerchiamo 'clobTokenIds' al posto di 'tokens'
                clob_token_ids = m.get("clobTokenIds", [])
                tokens_info = m.get("tokens", [])
                
                if isinstance(clob_token_ids, str):
                    import json
                    clob_token_ids = json.loads(clob_token_ids)
                
                parsed_tokens = []
                for idx, outcome_name in enumerate(outcomes):
                    token_id = None
                    # Controlliamo il nuovo formato
                    if clob_token_ids and idx < len(clob_token_ids):
                        token_id = clob_token_ids[idx]
                    # Controlliamo il vecchio formato come fallback
                    elif tokens_info and idx < len(tokens_info) and isinstance(tokens_info[idx], dict):
                        token_id = tokens_info[idx].get("token_id")
                        
                    if token_id:
                        parsed_tokens.append(Token(token_id=str(token_id), outcome=str(outcome_name)))
                
                if parsed_tokens:
                    parsed_markets.append(
                        Market(
                            condition_id=m.get("conditionId", m.get("id", "")),
                            question=m.get("question", "Mercato senza nome"),
                            tokens=parsed_tokens,
                            active=True,
                            closed=False
                        )
                    )
            except Exception as e:
                continue
                
        logger.info(f"Trovati e analizzati {len(parsed_markets)} mercati attivi.")
        return parsed_markets

    async def get_order_book(self, token_id: str) -> Optional[OrderBook]:
        """
        Interroga la CLOB API (Level 0 - Public) per scaricare gli ordini Limit attivi.
        """
        url = f"{self.clob_url}/book"
        params = {"token_id": token_id}
        
        async with self.semaphore:
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPError as e:
                logger.error(f"Errore CLOB API fetch book per token {token_id}: {e}")
                return None
                
        return OrderBook(
            token_id=token_id,
            timestamp=time.time(),
            bids=[OrderBookLevel(price=float(b.get("price")), size=float(b.get("size"))) for b in data.get("bids", [])],
            asks=[OrderBookLevel(price=float(a.get("price")), size=float(a.get("size"))) for a in data.get("asks", [])]
        )

    async def close(self):
        await self.client.close()