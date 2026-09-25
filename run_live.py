import asyncio
import logging
from pathlib import Path

import yaml

from src.core.models import PortfolioState
from src.data.polymarket_client import PolymarketDataClient
from src.data.websocket import PolymarketWSClient
from src.detectors.structural import IntraMarketArbDetector
from src.live.paper_trader import LivePaperTrader
from src.pricing.execution import PricingEngine
from src.risk.manager import RiskManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def load_settings() -> dict:
    with Path("config/settings.yaml").open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


async def main() -> None:
    settings = load_settings()
    api = settings["api"]
    trading = settings["trading"]

    data_client = PolymarketDataClient(
        gamma_url=api["gamma_url"],
        clob_url=api["clob_url"],
        concurrency_limit=int(api["rate_limit_concurrent_reqs"]),
        timeout_seconds=float(api["timeout_seconds"]),
    )

    logging.info("Scanning Gamma market metadata...")
    all_markets = []
    limit = 100
    offset = 0
    max_markets_to_track = 1500

    try:
        while len(all_markets) < max_markets_to_track:
            markets_chunk = await data_client.get_active_markets(limit=limit, offset=offset)
            if not markets_chunk:
                break
            all_markets.extend(markets_chunk)
            offset += limit
            await asyncio.sleep(0.2)

        target_markets = [
            market
            for market in all_markets
            if len(market.tokens) == 2 and market.active
        ][:max_markets_to_track]

        if not target_markets:
            logging.error("No binary active markets found.")
            return

        logging.info("Starting paper-trading surveillance on %d markets", len(target_markets))

        token_ids = [
            token.token_id
            for market in target_markets
            for token in market.tokens
        ]

        pricing_engine = PricingEngine(
            taker_fee_rate=float(trading["fallback_taker_fee_rate"])
        )
        detector = IntraMarketArbDetector(
            pricing_engine,
            max_cost_threshold=float(trading["arb_cost_threshold"]),
        )
        risk_manager = RiskManager(
            assumed_win_probability=float(trading["assumed_win_probability"])
        )
        portfolio = PortfolioState(
            total_balance=10_000.0,
            available_balance=10_000.0,
            max_exposure_per_trade=float(trading["max_exposure_per_trade"]),
            fractional_kelly_multiplier=float(trading["fractional_kelly_multiplier"]),
        )

        trader = LivePaperTrader(target_markets, [detector], risk_manager, portfolio)
        ws_client = PolymarketWSClient(
            token_ids=token_ids,
            on_message_callback=trader.process_ws_message,
        )

        ws_task = asyncio.create_task(ws_client.start())
        try:
            await asyncio.Event().wait()
        finally:
            await ws_client.stop()
            ws_task.cancel()
            try:
                await ws_task
            except asyncio.CancelledError:
                pass
    finally:
        await data_client.close()


if __name__ == "__main__":
    asyncio.run(main())
