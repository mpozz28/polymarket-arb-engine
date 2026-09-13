import pytest
import pandas as pd
from src.core.models import Market, Token, OrderBook, OrderBookLevel
from src.pricing.execution import PricingEngine
from src.detectors.structural import IntraMarketArbDetector
from src.risk.manager import RiskManager
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import PerformanceMetrics

def mock_data_generator():
    """Generatore event-driven per simulare il passaggio del tempo"""
    market = Market(
        condition_id="mkt_1", question="Event?", 
        tokens=[Token(token_id="Y", outcome="Yes"), Token(token_id="N", outcome="No")],
        active=True, closed=False
    )
    
    # TICK 1 (Time=100): Opportunità di arbitraggio!
    # Yes a 0.40, No a 0.50 -> Tot = 0.90
    books_t1 = {
        "Y": OrderBook(token_id="Y", timestamp=100.0, bids=[], asks=[OrderBookLevel(price=0.40, size=1000)]),
        "N": OrderBook(token_id="N", timestamp=100.0, bids=[], asks=[OrderBookLevel(price=0.50, size=1000)])
    }
    yield (100.0, market, books_t1)
    
    # TICK 2 (Time=200): Prezzi tornati alla normalità, l'arbitraggio è svanito.
    books_t2 = {
        "Y": OrderBook(token_id="Y", timestamp=200.0, bids=[], asks=[OrderBookLevel(price=0.60, size=1000)]),
        "N": OrderBook(token_id="N", timestamp=200.0, bids=[], asks=[OrderBookLevel(price=0.45, size=1000)])
    }
    yield (200.0, market, books_t2)
    
    # TICK 3 (Time=300): Il mercato si chiude (viene risolto dall'oracolo)
    market_closed = market.model_copy(update={"closed": True, "active": False})
    yield (300.0, market_closed, books_t2)

def test_full_backtest_loop():
    engine_pricing = PricingEngine(taker_fee_rate=0.0)
    detector = IntraMarketArbDetector(engine_pricing, max_cost_threshold=0.99)
    risk = RiskManager(assumed_win_probability=0.99)
    
    # Partiamo con 10.000$ (pUSD)
    backtester = BacktestEngine(initial_capital=10000.0, detectors=[detector], risk_manager=risk)
    
    # Facciamo girare la simulazione
    backtester.run(mock_data_generator())
    
    # ASSERTIONS
    assert len(backtester.trade_history) == 1
    trade = backtester.trade_history[0]
    
    # Al Tick 1 ha trovato l'opportunità a 0.90 per share.
    # Il Kelly Frazionario (Half Kelly) su 0.90 e Win Prob 0.99 suggerirebbe un'esposizione massiccia,
    # MA noi abbiamo l'hard cap del max_exposure_per_trade al 5%.
    # 5% di 10.000$ = 500$ di investimento massimo.
    assert trade.capital_invested == 500.0
    
    # Se investiamo 500$ a un costo medio di 0.90, compriamo 555.55 shares (quote)
    expected_shares = 500.0 / 0.90
    assert trade.expected_payout == pytest.approx(expected_shares * 1.00)
    
    # Il profitto generato è il Payout - Capitale Investito (circa 55.55$)
    locked_profit = (expected_shares * 1.0) - 500.0
    
    # Al termine del backtest, il mercato si è chiuso, quindi il profitto è stato accreditato!
    assert backtester.portfolio.total_balance == pytest.approx(10000.0 + locked_profit)
    assert backtester.portfolio.available_balance == backtester.portfolio.total_balance

def test_performance_metrics():
    # Simuliamo un vettore di rendimenti giornalieri di un mese (20 giorni)
    # 19 giorni guadagniamo lo 0.2%, 1 giorno perdiamo il 1%
    returns = [0.002] * 19 + [-0.01]
    series = pd.Series(returns)
    
    metrics = PerformanceMetrics.calculate_metrics(series, risk_free_rate=0.0)
    
    assert metrics["win_rate_pct"] == 95.0
    assert metrics["max_drawdown_pct"] < 0 # il drawdown è negativo
    assert metrics["sharpe_ratio"] > 0