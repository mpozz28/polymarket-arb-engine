import time
import logging
from typing import Dict, List, Any
from src.core.models import Market, OrderBook, OrderBookLevel, PortfolioState
from src.detectors.base import BaseDetector
from src.risk.manager import RiskManager

logger = logging.getLogger(__name__)

class LivePaperTrader:
    def __init__(self, markets: List[Market], detectors: List[BaseDetector], risk_manager: RiskManager, portfolio: PortfolioState):
        self.detectors = detectors
        self.risk_manager = risk_manager
        self.portfolio = portfolio
        
        # Mappiamo i token_id al rispettivo mercato per un lookup O(1) ultra-veloce
        self.markets_by_token: Dict[str, Market] = {}
        for m in markets:
            for t in m.tokens:
                self.markets_by_token[t.token_id] = m
                
        # Stato in memoria degli order book e cooldown
        self.order_books: Dict[str, OrderBook] = {}
        self.last_alert_time: Dict[str, float] = {}
        
    async def process_ws_message(self, data: Any):
        """
        Gestione robusta: smista i dati sia se Polymarket invia un dizionario singolo,
        sia se invia una lista di aggiornamenti in blocco.
        """
        if isinstance(data, list):
            for item in data:
                await self._parse_single_message(item)
        elif isinstance(data, dict):
            await self._parse_single_message(data)

    async def _parse_single_message(self, data: dict):
        # --- ⏱️ START CRONOMETRO ---
        start_time = time.perf_counter()
        
        # Estrazione sicura dell'ID (Polymarket usa formati misti)
        token_id = data.get("asset_id", data.get("token_id"))
        if not token_id:
            return
            
        market = self.markets_by_token.get(token_id)
        if not market:
            return # Token ignorato
            
        bids_raw = data.get("bids", [])
        asks_raw = data.get("asks", [])
        
        if bids_raw or asks_raw:
            # Aggiorniamo il book
            self.order_books[token_id] = OrderBook(
                token_id=token_id,
                timestamp=time.time(),
                bids=[OrderBookLevel(price=float(b["price"]), size=float(b["size"])) for b in bids_raw if "price" in b and "size" in b],
                asks=[OrderBookLevel(price=float(a["price"]), size=float(a["size"])) for a in asks_raw if "price" in a and "size" in a]
            )
            
            # Verifichiamo se abbiamo tutti i book necessari per QUESTO specifico mercato
            market_token_ids = [t.token_id for t in market.tokens]
            if all(tid in self.order_books for tid in market_token_ids):
                
                # Esecuzione dei calcoli (Spread Scanner + Kelly)
                self._evaluate_market(market)
                
                # --- ⏱️ STOP CRONOMETRO ---
                end_time = time.perf_counter()
                processing_time_ms = (end_time - start_time) * 1000
                
                # Stampiamo il tempo solo se è superiore a 1 millisecondo (evita di spammare micro-calcoli)
                if processing_time_ms > 1.0:
                    logger.info(f"⏱️ Latenza di calcolo (Tick-to-Trade): {processing_time_ms:.3f} ms")

    def _evaluate_market(self, market: Market):
        # --- AGGIUNTA PER TEST VISIVO: Scanner di Spread Live ---
        if len(market.tokens) == 2:
            t1, t2 = market.tokens[0].token_id, market.tokens[1].token_id
            book1, book2 = self.order_books.get(t1), self.order_books.get(t2)
            
            # Se entrambi i token hanno liquidità in vendita (asks)
            if book1 and book2 and book1.asks and book2.asks:
                best_ask1 = book1.asks[0].price
                best_ask2 = book2.asks[0].price
                spread_sum = best_ask1 + best_ask2
                
                if spread_sum < 1.05:
                    logger.info(f"📊 [LIVE SPREAD] {market.question[:50]}... | Totale: ${spread_sum:.3f} (Sì: {best_ask1:.2f} + No: {best_ask2:.2f})")
        # --------------------------------------------------------

        # Esecuzione classica del Detector di Arbitraggio
        for detector in self.detectors:
            opportunities = detector.detect(market, self.order_books)
            for opp in opportunities:
                trade = self.risk_manager.evaluate_opportunity(opp, self.portfolio)
                if trade.approved_capital > 0:
                    self._execute_paper_trade(trade, market)

    def _execute_paper_trade(self, trade, market: Market):
        current_time = time.time()
        # Cooldown di 10 secondi per lo stesso mercato per non spammare la console
        if current_time - self.last_alert_time.get(market.condition_id, 0) < 10.0:
            return
            
        self.last_alert_time[market.condition_id] = current_time
        
        logger.info("="*60)
        logger.info(f"🚨 OPPORTUNITÀ MULTI-MARKET: {market.question}")
        logger.info(f"Costo medio per share: ${trade.opportunity.total_capital_required/trade.opportunity.max_executable_size:.4f} (Max Size eseguibile: {trade.opportunity.max_executable_size:.1f})")
        logger.info(f"Capitale allocato (Kelly): ${trade.approved_capital:.2f} ({trade.reason})")
        logger.info(f"Net PnL Atteso: ${trade.opportunity.expected_net_pnl:.2f} (ROI: {trade.opportunity.expected_roi_bps/100:.2f}%)")
        logger.info("="*60)
    