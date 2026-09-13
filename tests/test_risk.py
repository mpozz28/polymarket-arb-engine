import pytest
from src.core.models import Opportunity, ArbLeg, OrderSide, PortfolioState
from src.risk.manager import RiskManager

@pytest.fixture
def sample_opportunity():
    # Simuliamo un'opportunità di arbitraggio eccellente: 
    # Compriamo 10.000 quote al costo medio di 0.95$ per quota (profitto netto = 500$)
    return Opportunity(
        market_id="mkt_1",
        strategy_name="IntraMarketArb",
        timestamp=1600000000.0,
        max_executable_size=10000.0,
        total_capital_required=9500.0, 
        expected_net_pnl=500.0,
        expected_roi_bps=526.0, # ~5.26%
        legs=[
            ArbLeg(token_id="yes", side=OrderSide.BUY, size=10000.0, expected_vwap=0.45),
            ArbLeg(token_id="no", side=OrderSide.BUY, size=10000.0, expected_vwap=0.50)
        ]
    )

def test_kelly_fraction_logic():
    risk_mgr = RiskManager(assumed_win_probability=0.99)
    # Payout = 1.0, Costo = 0.95
    # Odds (b) = (1.0 - 0.95) / 0.95 = 0.05 / 0.95 = 0.05263
    # Kelly = 0.99 - (0.01 / 0.05263) = 0.99 - 0.19 = 0.80 (80% del portafoglio!)
    f = risk_mgr.calculate_kelly_fraction(win_prob=0.99, cost_per_share=0.95)
    assert f == pytest.approx(0.80, rel=1e-2)

def test_risk_manager_capped_by_exposure(sample_opportunity):
    portfolio = PortfolioState(
        total_balance=100000.0,       # 100k di capitale
        available_balance=100000.0,
        max_exposure_per_trade=0.05,  # Max 5% = 5.000$ per trade
        fractional_kelly_multiplier=0.5 # Half Kelly = 40% del portafoglio (Ignorato perchè 5% è minore)
    )
    
    risk_mgr = RiskManager(assumed_win_probability=0.99)
    approved = risk_mgr.evaluate_opportunity(sample_opportunity, portfolio)
    
    # Kelly direbbe 40k, l'Order Book consente 9.5k, ma il nostro limite hard è 5k!
    assert approved.approved_capital == 5000.0
    assert approved.reason == "Capped by max exposure limit"
    # Se investiamo 5000$ invece di 9500$, la size scende proporzionalmente
    assert approved.approved_size == pytest.approx((5000.0 / 9500.0) * 10000.0)

def test_risk_manager_capped_by_order_book(sample_opportunity):
    portfolio = PortfolioState(
        total_balance=1000000.0,      # 1 Milione di capitale
        available_balance=1000000.0,
        max_exposure_per_trade=0.10,  # Max 10% = 100.000$
        fractional_kelly_multiplier=1.0 # Full Kelly
    )
    
    risk_mgr = RiskManager(assumed_win_probability=0.99)
    approved = risk_mgr.evaluate_opportunity(sample_opportunity, portfolio)
    
    # Abbiamo 100k disponibili per il trade e Kelly ci dà il via libera, 
    # ma l'Order Book offre solo 9.500$ di liquidità
    assert approved.approved_capital == 9500.0
    assert approved.approved_size == 10000.0
    assert approved.reason == "Fully executed up to Order Book limits"