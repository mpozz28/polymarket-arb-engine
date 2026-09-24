from src.core.models import ApprovedTrade, Opportunity, PortfolioState


class RiskManager:
    def __init__(self, assumed_win_probability: float = 0.99):
        """
        assumed_win_probability: 
        In un arbitraggio perfetto è 1.0. Tuttavia, per via dell'Oracle Risk 
        (rischio che il mercato venga invalidato o risolto in modo anomalo),
        impostiamo un valore prudenziale come 0.99 (99% probabilità di successo).
        """
        self.assumed_win_probability = assumed_win_probability

    def calculate_kelly_fraction(self, win_prob: float, cost_per_share: float, payout_per_share: float = 1.0) -> float:
        """
        Calcola la percentuale ottimale di portafoglio da investire usando la formula di Kelly.
        K = p - ((1 - p) / b)
        dove:
        p = probabilità di vincita
        b = odds (Profitto potenziale / Perdita potenziale)
        """
        if cost_per_share >= payout_per_share or cost_per_share <= 0:
            return 0.0 # Non è un arbitraggio profittevole
            
        profit_per_share = payout_per_share - cost_per_share
        loss_per_share = cost_per_share # Se il mercato fallisce/viene annullato, perdi il costo
        
        # Le "odds" b che riceviamo dal mercato
        b = profit_per_share / loss_per_share
        
        # Formula di Kelly
        kelly_f = win_prob - ((1.0 - win_prob) / b)
        
        return max(0.0, kelly_f)

    def evaluate_opportunity(self, opp: Opportunity, portfolio: PortfolioState) -> ApprovedTrade:
        """
        Valuta un'opportunità e decide quanto capitale allocare.
        Applica Kelly, lo dimezza (Half-Kelly) e lo scontra con gli Hard Limits.
        """
        # 1. Calcolo del costo medio per "quota" (share) dall'opportunità
        cost_per_share = opp.total_capital_required / opp.max_executable_size
        
        # 2. Calcolo percentuale teorica secondo Kelly
        kelly_f = self.calculate_kelly_fraction(
            win_prob=self.assumed_win_probability,
            cost_per_share=cost_per_share
        )
        
        # 3. Applicazione moltiplicatore frazionario (es. Half-Kelly per ridurre la volatilità)
        adjusted_kelly_f = kelly_f * portfolio.fractional_kelly_multiplier
        
        # 4. Calcolo capitale suggerito da Kelly
        kelly_capital = portfolio.total_balance * adjusted_kelly_f
        
        # 5. Applicazione degli Hard Limit (vincoli di sicurezza)
        max_exposure_capital = portfolio.total_balance * portfolio.max_exposure_per_trade
        
        # Non possiamo investire più di:
        # A) Quello che suggerisce Kelly
        # B) Il nostro limite aziendale/personale (es. 5% AUM)
        # C) La liquidità disponibile sull'exchange
        # D) La liquidità dell'Order Book per quel trade (opp.total_capital_required)
        
        approved_capital = min(
            kelly_capital,
            max_exposure_capital,
            portfolio.available_balance,
            opp.total_capital_required
        )
        
        # Ricalcolo della size (quote) in base al capitale approvato
        if approved_capital == opp.total_capital_required:
            approved_size = opp.max_executable_size
            reason = "Fully executed up to Order Book limits"
        elif approved_capital == max_exposure_capital:
            approved_size = (approved_capital / opp.total_capital_required) * opp.max_executable_size
            reason = "Capped by max exposure limit"
        elif approved_capital == portfolio.available_balance:
            approved_size = (approved_capital / opp.total_capital_required) * opp.max_executable_size
            reason = "Capped by available balance"
        else:
            approved_size = (approved_capital / opp.total_capital_required) * opp.max_executable_size
            reason = "Capped by Fractional Kelly"

        return ApprovedTrade(
            opportunity=opp,
            approved_capital=approved_capital,
            approved_size=approved_size,
            kelly_fraction_suggested=adjusted_kelly_f,
            reason=reason
        )