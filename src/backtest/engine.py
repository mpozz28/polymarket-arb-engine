import pandas as pd
from typing import List, Dict, Iterator, Tuple
from src.core.models import Market, OrderBook, PortfolioState, ApprovedTrade
from src.detectors.base import BaseDetector
from src.risk.manager import RiskManager

class TradeRecord:
    def __init__(self, timestamp: float, trade: ApprovedTrade):
        self.timestamp = timestamp
        self.market_id = trade.opportunity.market_id
        self.capital_invested = trade.approved_capital
        self.expected_payout = trade.approved_size * 1.00 # Il contratto vincente paga 1$
        self.locked_profit = self.expected_payout - self.capital_invested
        self.resolved = False

class BacktestEngine:
    def __init__(self, initial_capital: float, detectors: List[BaseDetector], risk_manager: RiskManager):
        self.portfolio = PortfolioState(
            total_balance=initial_capital,
            available_balance=initial_capital,
            max_exposure_per_trade=0.05,
            fractional_kelly_multiplier=0.5
        )
        self.detectors = detectors
        self.risk_manager = risk_manager
        
        self.active_trades: List[TradeRecord] = []
        self.trade_history: List[TradeRecord] = []
        self.equity_curve: List[Tuple[float, float]] = [] # [(timestamp, total_balance)]

    def resolve_market(self, market_id: str, timestamp: float):
        """
        Simula la chiusura del mercato. Il capitale bloccato torna disponibile 
        più il profitto generato dall'arbitraggio.
        """
        for trade in self.active_trades:
            if trade.market_id == market_id and not trade.resolved:
                trade.resolved = True
                # Aggiungiamo il profitto al bilancio totale
                self.portfolio.total_balance += trade.locked_profit
                # Ripristiniamo il capitale disponibile (capitale investito + profitto)
                self.portfolio.available_balance += trade.expected_payout
                
                # Registriamo l'evento sulla curva
                self.equity_curve.append((timestamp, self.portfolio.total_balance))

        # Rimuove i trade risolti dalla lista attiva
        self.active_trades = [t for t in self.active_trades if not t.resolved]

    def run(self, data_feed: Iterator[Tuple[float, Market, Dict[str, OrderBook]]]):
        """
        data_feed: Un generatore (Yield) che sputa (timestamp, market_snapshot, order_books).
        Questo previene il lookahead bias.
        """
        self.equity_curve.append((0, self.portfolio.total_balance)) # Stato iniziale

        for current_time, market, order_books in data_feed:
            
            # 1. Se il mercato è chiuso, risolviamo eventuali trade aperti per quel mercato
            if market.closed:
                self.resolve_market(market.condition_id, current_time)
                continue

            # 2. Eseguiamo tutti i detector configurati
            for detector in self.detectors:
                opportunities = detector.detect(market, order_books)
                
                for opp in opportunities:
                    # 3. Passiamo l'opportunità al Risk Manager
                    approved_trade = self.risk_manager.evaluate_opportunity(opp, self.portfolio)
                    
                    # 4. Esecuzione virtuale se approvata
                    if approved_trade.approved_capital > 0:
                        self.execute_trade(current_time, approved_trade)

    def execute_trade(self, timestamp: float, trade: ApprovedTrade):
        """
        Simula il piazzamento dell'ordine sottraendo il capitale disponibile.
        Nota: In un arbitraggio strutturale copriamo tutti gli esiti. 
        Siamo market-neutral, quindi incasseremo 1.00$ per share matematica a scadenza.
        """
        # Blocchiamo il capitale
        self.portfolio.available_balance -= trade.approved_capital
        
        record = TradeRecord(timestamp, trade)
        self.active_trades.append(record)
        self.trade_history.append(record)