
from src.core.models import ExecutionSimulation, OrderBook, OrderSide


class PricingEngine:
    """Executable pricing, slippage and fee calculations."""

    def __init__(self, taker_fee_rate: float = 0.0):
        self.taker_fee_rate = max(0.0, taker_fee_rate)

    @staticmethod
    def taker_fee_usd(shares: float, price: float, fee_rate: float) -> float:
        """Polymarket documented fee curve: C * feeRate * p * (1-p)."""
        if shares <= 0 or price <= 0 or price >= 1 or fee_rate <= 0:
            return 0.0
        return shares * fee_rate * price * (1.0 - price)

    def effective_price(
        self,
        price: float,
        fee_rate: float | None = None,
        side: OrderSide = OrderSide.BUY,
    ) -> float:
        rate = self.taker_fee_rate if fee_rate is None else max(0.0, fee_rate)
        fee = self.taker_fee_usd(1.0, price, rate)
        if side == OrderSide.BUY:
            return price + fee
        return price - fee

    def simulate_market_order(
        self,
        book: OrderBook,
        side: OrderSide,
        target_size: float,
        fee_rate: float | None = None,
    ) -> ExecutionSimulation:
        if target_size <= 0:
            raise ValueError("target_size must be greater than zero")

        rate = self.taker_fee_rate if fee_rate is None else max(0.0, fee_rate)
        levels = list(book.asks if side == OrderSide.BUY else book.bids)
        sorted_levels = sorted(levels, key=lambda level: level.price, reverse=side == OrderSide.SELL)

        if not sorted_levels:
            return self._empty_simulation(side, target_size)

        best_price = sorted_levels[0].price
        remaining_size = target_size
        total_cost = 0.0
        executed_size = 0.0
        fees = 0.0

        for level in sorted_levels:
            if remaining_size <= 0:
                break
            fill_size = min(remaining_size, level.size)
            executed_size += fill_size
            total_cost += fill_size * level.price
            fees += self.taker_fee_usd(fill_size, level.price, rate)
            remaining_size -= fill_size

        if executed_size <= 0:
            return self._empty_simulation(side, target_size)

        vwap = total_cost / executed_size
        slippage_bps = (
            abs((vwap - best_price) / best_price) * 10_000.0
            if best_price > 0
            else 0.0
        )

        return ExecutionSimulation(
            side=side,
            requested_size=target_size,
            executed_size=executed_size,
            vwap_price=vwap,
            total_cost=total_cost,
            fees_paid=fees,
            slippage_bps=slippage_bps,
            is_fully_filled=remaining_size <= 1e-12,
        )

    def calculate_max_arb_size(
        self,
        yes_book: OrderBook,
        no_book: OrderBook,
        max_cost_threshold: float = 0.99,
        fee_rate: float | None = None,
    ) -> float:
        rate = self.taker_fee_rate if fee_rate is None else max(0.0, fee_rate)
        yes_asks = sorted(yes_book.asks, key=lambda level: level.price)
        no_asks = sorted(no_book.asks, key=lambda level: level.price)

        if not yes_asks or not no_asks:
            return 0.0

        total_shares = 0.0
        yes_idx = 0
        no_idx = 0
        yes_remaining = yes_asks[0].size
        no_remaining = no_asks[0].size

        while yes_idx < len(yes_asks) and no_idx < len(no_asks):
            yes_price = yes_asks[yes_idx].price
            no_price = no_asks[no_idx].price
            combined_effective = (
                self.effective_price(yes_price, rate, OrderSide.BUY)
                + self.effective_price(no_price, rate, OrderSide.BUY)
            )

            if combined_effective >= max_cost_threshold:
                break

            step_size = min(yes_remaining, no_remaining)
            if step_size <= 0:
                break

            total_shares += step_size
            yes_remaining -= step_size
            no_remaining -= step_size

            if yes_remaining <= 1e-12:
                yes_idx += 1
                if yes_idx < len(yes_asks):
                    yes_remaining = yes_asks[yes_idx].size

            if no_remaining <= 1e-12:
                no_idx += 1
                if no_idx < len(no_asks):
                    no_remaining = no_asks[no_idx].size

        return total_shares

    @staticmethod
    def _empty_simulation(side: OrderSide, target_size: float) -> ExecutionSimulation:
        return ExecutionSimulation(
            side=side,
            requested_size=target_size,
            executed_size=0.0,
            vwap_price=0.0,
            total_cost=0.0,
            fees_paid=0.0,
            slippage_bps=0.0,
            is_fully_filled=False,
        )
