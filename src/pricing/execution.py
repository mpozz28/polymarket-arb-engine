from typing import List
from src.core.models import OrderBook, OrderBookLevel, OrderSide, ExecutionSimulation

class PricingEngine:
    def __init__(self, taker_fee_rate: float = 0.00):
        """
        taker_fee_rate: percentuale (es. 0.001 per 0.1%). 
        Attualmente Polymarket ha spesso 0% di fee di trading, ma lo rendiamo configurabile.
        """
        self.taker_fee_rate = taker_fee_rate

    def simulate_market_order(self, book: OrderBook, side: OrderSide, target_size: float) -> ExecutionSimulation:
        """
        Simula l'esecuzione di un ordine a mercato percorrendo il book (Order Book Walking).
        Restituisce un report dettagliato su prezzo medio, costo e slippage.
        """
        if target_size <= 0:
            raise ValueError("Target size deve essere maggiore di zero.")

        # Se compriamo, dobbiamo consumare gli Asks (ordinati dal prezzo più basso al più alto)
        # Se vendiamo, dobbiamo consumare i Bids (ordinati dal prezzo più alto al più basso)
        levels = book.asks if side == OrderSide.BUY else book.bids
        
        # Assicuriamoci che i livelli siano ordinati correttamente.
        # Spesso l'API li restituisce già ordinati, ma noi non ci fidiamo mai dei dati esterni.
        reverse_sort = True if side == OrderSide.SELL else False
        sorted_levels = sorted(levels, key=lambda x: x.price, reverse=reverse_sort)

        if not sorted_levels:
            # Book vuoto
            return self._empty_simulation(side, target_size)

        best_price = sorted_levels[0].price
        remaining_size = target_size
        total_cost = 0.0
        executed_size = 0.0

        for level in sorted_levels:
            if remaining_size <= 0:
                break

            fill_size = min(remaining_size, level.size)
            executed_size += fill_size
            total_cost += fill_size * level.price
            remaining_size -= fill_size

        if executed_size == 0:
            return self._empty_simulation(side, target_size)

        vwap = total_cost / executed_size
        fees = total_cost * self.taker_fee_rate
        
        # Calcolo Slippage in BPS (Basis Points)
        # BPS formula: |(VWAP - Best Price) / Best Price| * 10,000
        slippage_bps = abs((vwap - best_price) / best_price) * 10000 if best_price > 0 else 0.0

        return ExecutionSimulation(
            side=side,
            requested_size=target_size,
            executed_size=executed_size,
            vwap_price=vwap,
            total_cost=total_cost,
            fees_paid=fees,
            slippage_bps=slippage_bps,
            is_fully_filled=(remaining_size == 0)
        )

    def calculate_max_arb_size(self, yes_book: OrderBook, no_book: OrderBook, max_cost_threshold: float = 0.99) -> float:
        """
        Funzione quantitativa avanzata:
        Calcola la size massima eseguibile per un arbitraggio complementare ("Sì" + "No")
        prima che l'aumento dei prezzi (slippage combinato) superi il threshold di profitto.
        Ritorna il numero di quote che possiamo comprare.
        """
        # Questa logica verrà estesa nel Modulo 3 (Detectors), ma qui gettiamo le basi.
        # L'algoritmo cammina simultaneamente su entrambi i book.
        
        # Ordinamento Asks
        yes_asks = sorted(yes_book.asks, key=lambda x: x.price)
        no_asks = sorted(no_book.asks, key=lambda x: x.price)
        
        total_executable_shares = 0.0
        y_idx, n_idx = 0, 0
        
        # Creiamo copie della size dei livelli correnti per non mutare i dati originali
        current_y_size = yes_asks[y_idx].size if yes_asks else 0
        current_n_size = no_asks[n_idx].size if no_asks else 0

        while y_idx < len(yes_asks) and n_idx < len(no_asks):
            current_y_price = yes_asks[y_idx].price
            current_n_price = no_asks[n_idx].price
            
            combined_price = current_y_price + current_n_price
            
            # Se aggiungendo le fee il costo totale di comprare 1 quota Yes e 1 No supera il limite, ci fermiamo
            net_combined_price = combined_price * (1 + self.taker_fee_rate)
            if net_combined_price >= max_cost_threshold:
                break
                
            # Possiamo comprare il minimo tra la size disponibile sui due rami
            step_size = min(current_y_size, current_n_size)
            total_executable_shares += step_size
            
            current_y_size -= step_size
            current_n_size -= step_size
            
            # Se abbiamo esaurito un livello, passiamo al successivo
            if current_y_size == 0:
                y_idx += 1
                if y_idx < len(yes_asks):
                    current_y_size = yes_asks[y_idx].size
                    
            if current_n_size == 0:
                n_idx += 1
                if n_idx < len(no_asks):
                    current_n_size = no_asks[n_idx].size

        return total_executable_shares

    def _empty_simulation(self, side: OrderSide, target_size: float) -> ExecutionSimulation:
        return ExecutionSimulation(
            side=side,
            requested_size=target_size,
            executed_size=0.0,
            vwap_price=0.0,
            total_cost=0.0,
            fees_paid=0.0,
            slippage_bps=0.0,
            is_fully_filled=False
        )

