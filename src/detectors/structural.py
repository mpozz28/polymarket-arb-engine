import time

from src.core.models import ArbLeg, Market, Opportunity, OrderBook, OrderSide
from src.detectors.base import BaseDetector
from src.pricing.execution import PricingEngine


class IntraMarketArbDetector(BaseDetector):
    def __init__(self, pricing_engine: PricingEngine, max_cost_threshold: float = 0.99):
        super().__init__(pricing_engine)
        self.max_cost_threshold = max_cost_threshold

    def detect(self, market: Market, order_books: dict[str, OrderBook]) -> list[Opportunity]:
        if not market.active or market.closed or len(market.tokens) != 2:
            return []

        token_ids = [token.token_id for token in market.tokens]
        if not all(token_id in order_books for token_id in token_ids):
            return []

        yes_book = order_books[token_ids[0]]
        no_book = order_books[token_ids[1]]
        if not yes_book.asks or not no_book.asks:
            return []

        fee_rate = market.taker_fee_rate if market.fees_enabled else 0.0
        best_combined = (
            self.pricing_engine.effective_price(yes_book.best_ask, fee_rate, OrderSide.BUY)
            + self.pricing_engine.effective_price(no_book.best_ask, fee_rate, OrderSide.BUY)
        )
        if best_combined >= self.max_cost_threshold:
            return []

        max_size = self.pricing_engine.calculate_max_arb_size(
            yes_book,
            no_book,
            max_cost_threshold=self.max_cost_threshold,
            fee_rate=fee_rate,
        )
        if max_size <= 0:
            return []

        sim_yes = self.pricing_engine.simulate_market_order(
            yes_book, OrderSide.BUY, max_size, fee_rate=fee_rate
        )
        sim_no = self.pricing_engine.simulate_market_order(
            no_book, OrderSide.BUY, max_size, fee_rate=fee_rate
        )

        if sim_yes.executed_size < max_size or sim_no.executed_size < max_size:
            return []

        total_cost = sim_yes.net_cost + sim_no.net_cost
        payout = max_size
        net_pnl = payout - total_cost
        if net_pnl <= 0:
            return []

        roi_bps = (net_pnl / total_cost) * 10_000.0 if total_cost > 0 else 0.0

        return [
            Opportunity(
                market_id=market.condition_id,
                strategy_name=self.strategy_name,
                timestamp=time.time(),
                max_executable_size=max_size,
                total_capital_required=total_cost,
                expected_net_pnl=net_pnl,
                expected_roi_bps=roi_bps,
                legs=[
                    ArbLeg(
                        token_id=token_ids[0],
                        side=OrderSide.BUY,
                        size=max_size,
                        expected_vwap=sim_yes.vwap_price,
                    ),
                    ArbLeg(
                        token_id=token_ids[1],
                        side=OrderSide.BUY,
                        size=max_size,
                        expected_vwap=sim_no.vwap_price,
                    ),
                ],
            )
        ]
