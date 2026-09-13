import time
from typing import List, Dict
from src.core.models import Market, OrderBook, Opportunity, ArbLeg, OrderSide
from src.detectors.base import BaseDetector
from src.pricing.execution import PricingEngine

class IntraMarketArbDetector(BaseDetector):
    def __init__(self, pricing_engine: PricingEngine, max_cost_threshold: float = 0.99):
        super().__init__(pricing_engine)
        self.max_cost_threshold = max_cost_threshold

    def detect(self, market: Market, order_books: Dict[str, OrderBook]) -> List[Opportunity]:
        opportunities = []

        # Controllo base: servono i dati per tutti i token del mercato
        if not market.active or market.closed:
            return opportunities
            
        token_ids = [t.token_id for t in market.tokens]
        if not all(t_id in order_books for t_id in token_ids):
            return opportunities # Mancano order book per alcuni outcome
            
        # Logica per mercati Binari (Yes/No)
        if len(token_ids) == 2:
            yes_id, no_id = token_ids[0], token_ids[1]
            yes_book, no_book = order_books[yes_id], order_books[no_id]
            
            # Check istantaneo al best_ask (costa pochissimo calcolarlo)
            best_combined = yes_book.best_ask + no_book.best_ask
            
            # Se nemmeno il best price genera profitto, scartiamo subito l'evento 
            # (risparmia CPU preziosa, fondamentale nei sistemi ad alta frequenza)
            if best_combined >= self.max_cost_threshold:
                return opportunities
                
            # Se siamo qui, ESISTE un'opportunità teorica. Ora calcoliamo lo SLIPPAGE REALE.
            max_size = self.pricing_engine.calculate_max_arb_size(
                yes_book, no_book, self.max_cost_threshold
            )
            
            if max_size <= 0:
                return opportunities # Falso allarme dovuto a fee o liquidità zero
                
            # Simuliamo l'esecuzione reale per calcolare i costi esatti
            sim_yes = self.pricing_engine.simulate_market_order(yes_book, OrderSide.BUY, max_size)
            sim_no = self.pricing_engine.simulate_market_order(no_book, OrderSide.BUY, max_size)
            
            total_cost = sim_yes.net_cost + sim_no.net_cost
            payout = max_size * 1.00 # Il contratto vincente paga 1$
            net_pnl = payout - total_cost
            
            if net_pnl > 0:
                roi_bps = (net_pnl / total_cost) * 10000 if total_cost > 0 else 0
                
                opp = Opportunity(
                    market_id=market.condition_id,
                    strategy_name=self.strategy_name,
                    timestamp=time.time(),
                    max_executable_size=max_size,
                    total_capital_required=total_cost,
                    expected_net_pnl=net_pnl,
                    expected_roi_bps=roi_bps,
                    legs=[
                        ArbLeg(token_id=yes_id, side=OrderSide.BUY, size=max_size, expected_vwap=sim_yes.vwap_price),
                        ArbLeg(token_id=no_id, side=OrderSide.BUY, size=max_size, expected_vwap=sim_no.vwap_price)
                    ]
                )
                opportunities.append(opp)

        # NB: In futuro qui si può aggiungere un elif len(token_ids) > 2 per i mercati multi-outcome
        # (es. "Chi vince le elezioni?": Trump, Harris, Altro)
        
        return opportunities