import asyncio
import json
import logging
from typing import List, Callable, Awaitable
import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

class PolymarketWSClient:
    def __init__(self, token_ids: List[str], on_message_callback: Callable[[dict], Awaitable[None]]):
        # Endpoint ufficiale per sottoscrizioni pubbliche (L0) al CLOB V2
        self.ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        self.token_ids = token_ids
        self.on_message_callback = on_message_callback
        self.is_running = False

    async def start(self):
        self.is_running = True
        reconnect_delay = 1.0

        while self.is_running:
            try:
                logger.info(f"Connessione a {self.ws_url} in corso...")
                async with websockets.connect(self.ws_url, max_size=None) as websocket:
                    logger.info("WebSocket connesso! Invio sottoscrizioni in batch...")
                    
                    # Chunking: Dividiamo i token_ids in gruppi da 100
                    chunk_size = 100
                    for i in range(0, len(self.token_ids), chunk_size):
                        chunk = self.token_ids[i:i + chunk_size]
                        subscribe_msg = {
                            "assets_ids": chunk,
                            "type": "market"
                        }
                        await websocket.send(json.dumps(subscribe_msg))
                        await asyncio.sleep(0.1) # Evita il rate limit del WS
                        
                    logger.info(f"Tutte le {len(self.token_ids)} sottoscrizioni inviate con successo!")
                    reconnect_delay = 1.0 
                    
                    async for message in websocket:
                        try:
                            # Ignoriamo messaggi vuoti o keep-alive non JSON
                            if not message or not message.strip():
                                continue
                                
                            data = json.loads(message)
                            await self.on_message_callback(data)
                            
                        except json.JSONDecodeError:
                            # Se il server manda testo grezzo o errori di rate-limit, lo registriamo senza crashare
                            logger.debug(f"Ricevuto frame non JSON dal WS: {message[:100]}")
                        except Exception as ex:
                            logger.error(f"Errore imprevisto nel processing del messaggio WS: {ex}")
                        
            except (ConnectionClosed, Exception) as e:
                if self.is_running:
                    logger.warning(f"WebSocket disconnesso ({e}). Riconnessione in {reconnect_delay}s...")
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, 30.0)

    async def stop(self):
        self.is_running = False
        logger.info("Chiusura WebSocket richiesta.")