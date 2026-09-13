import asyncio
import logging
from src.data.polymarket_client import PolymarketDataClient
from src.pricing.execution import PricingEngine
from src.detectors.structural import IntraMarketArbDetector
from src.risk.manager import RiskManager
from src.core.models import PortfolioState
from src.data.websocket import PolymarketWSClient
from src.live.paper_trader import LivePaperTrader


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    data_client = PolymarketDataClient(gamma_url="https://gamma-api.polymarket.com", clob_url="https://clob.polymarket.com")
    
    logging.info("Inizio scansione globale del database Gamma API...")
    all_markets = []
    limit = 100
    offset = 0
    max_markets_to_track = 1500 # Limite di sicurezza per la CPU
    
    while True:
        logging.info(f"Scaricamento mercati da offset {offset}...")
        markets_chunk = await data_client.get_active_markets(limit=limit, offset=offset)
        
        if not markets_chunk:
            break # Abbiamo raggiunto la fine del database
            
        all_markets.extend(markets_chunk)
        offset += limit
        
        # Filtriamo subito i binari per vedere a quanti siamo
        binaries = [m for m in all_markets if len(m.tokens) == 2]
        if len(binaries) >= max_markets_to_track:
            logging.info(f"Raggiunto il limite massimo di sicurezza ({max_markets_to_track}).")
            break
            
        await asyncio.sleep(0.2) # Pausa per non farsi bannare l'IP (Rate Limiting)
        
    await data_client.close()
    
    target_markets = [m for m in all_markets if len(m.tokens) == 2][:max_markets_to_track]
    
    if not target_markets:
        logging.error("Nessun mercato binario trovato.")
        return
        
    logging.info(f"🌐 RETE GLOBALE ATTIVATA: Monitoraggio simultaneo di {len(target_markets)} mercati!")
    
    token_ids = []
    for m in target_markets:
        token_ids.extend([t.token_id for t in m.tokens])
        
    pricing_engine = PricingEngine(taker_fee_rate=0.0) 
    detector = IntraMarketArbDetector(pricing_engine, max_cost_threshold=0.99)
    risk_manager = RiskManager(assumed_win_probability=0.99)
    portfolio = PortfolioState(
        total_balance=10000.0,
        available_balance=10000.0,
        max_exposure_per_trade=0.05,
        fractional_kelly_multiplier=0.5
    )
            
    trader = LivePaperTrader(target_markets, [detector], risk_manager, portfolio)
    ws_client = PolymarketWSClient(token_ids=token_ids, on_message_callback=trader.process_ws_message)
    
    task = asyncio.create_task(ws_client.start())
    
    try:
        logging.info(f"Sistema in ascolto su {len(token_ids)} token. Premi Ctrl+C per fermare...")
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        logging.info("Arresto manuale del sistema...")
    finally:
        await ws_client.stop()
        task.cancel()

if __name__ == "__main__":
    asyncio.run(main())