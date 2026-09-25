import asyncio
import json
import logging
import time
from typing import Any

from curl_cffi.requests import AsyncSession

from src.core.models import Market, OrderBook, OrderBookLevel, Token

logger = logging.getLogger(__name__)


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class PolymarketDataClient:
    """Read-only asynchronous client for Gamma market metadata and CLOB order books."""

    def __init__(
        self,
        gamma_url: str,
        clob_url: str,
        concurrency_limit: int = 50,
        timeout_seconds: float = 15.0,
    ):
        self.gamma_url = gamma_url.rstrip("/")
        self.clob_url = clob_url.rstrip("/")
        self.client = AsyncSession(
            impersonate="chrome110",
            timeout=timeout_seconds,
            verify=True,
        )
        self.semaphore = asyncio.Semaphore(concurrency_limit)

    async def get_active_markets(self, limit: int = 50, offset: int = 0) -> list[Market]:
        url = f"{self.gamma_url}/markets"
        params = {"limit": limit, "offset": offset}

        async with self.semaphore:
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            except (ConnectionError, TimeoutError, ValueError, OSError) as exc:
                logger.error("Gamma API request failed: %s", exc)
                return []

        if isinstance(data, dict):
            data = data.get("data", data.get("markets", []))

        if not isinstance(data, list):
            logger.error("Unrecognized Gamma API response format")
            return []

        parsed_markets: list[Market] = []

        for raw_market in data:
            if not isinstance(raw_market, dict):
                continue
            if _parse_bool(raw_market.get("closed"), False):
                continue

            try:
                outcomes = raw_market.get("outcomes", [])
                if isinstance(outcomes, str):
                    outcomes = json.loads(outcomes)

                clob_token_ids = raw_market.get("clobTokenIds", [])
                if isinstance(clob_token_ids, str):
                    clob_token_ids = json.loads(clob_token_ids)

                legacy_tokens = raw_market.get("tokens", [])
                tokens: list[Token] = []

                for idx, outcome_name in enumerate(outcomes):
                    token_id = None
                    if clob_token_ids and idx < len(clob_token_ids):
                        token_id = clob_token_ids[idx]
                    elif (
                        legacy_tokens
                        and idx < len(legacy_tokens)
                        and isinstance(legacy_tokens[idx], dict)
                    ):
                        token_id = legacy_tokens[idx].get("token_id")

                    if token_id:
                        tokens.append(
                            Token(token_id=str(token_id), outcome=str(outcome_name))
                        )

                if not tokens:
                    continue

                fee_schedule = raw_market.get("feeSchedule", {})
                if isinstance(fee_schedule, str):
                    try:
                        fee_schedule = json.loads(fee_schedule)
                    except json.JSONDecodeError:
                        fee_schedule = {}
                if not isinstance(fee_schedule, dict):
                    fee_schedule = {}

                fee_rate = _parse_float(
                    raw_market.get(
                        "takerFeeRate",
                        raw_market.get("feeRate", fee_schedule.get("rate", 0.0)),
                    )
                )
                if fee_rate > 1.0:
                    fee_rate /= 10_000.0

                parsed_markets.append(
                    Market(
                        condition_id=str(raw_market.get("conditionId", raw_market.get("id", ""))),
                        question=str(raw_market.get("question", "Unnamed market")),
                        tokens=tokens,
                        active=_parse_bool(raw_market.get("active"), True),
                        closed=False,
                        market_type="binary" if len(tokens) == 2 else "categorical",
                        fees_enabled=_parse_bool(raw_market.get("feesEnabled"), False),
                        taker_fee_rate=max(0.0, fee_rate),
                    )
                )
            except (TypeError, ValueError, json.JSONDecodeError):
                logger.debug("Skipping malformed market payload", exc_info=True)

        logger.info("Parsed %d active markets", len(parsed_markets))
        return parsed_markets

    async def get_order_book(self, token_id: str) -> OrderBook | None:
        url = f"{self.clob_url}/book"
        params = {"token_id": token_id}

        async with self.semaphore:
            try:
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
            except (ConnectionError, TimeoutError, ValueError, OSError) as exc:
                logger.error("CLOB book request failed for %s: %s", token_id, exc)
                return None

        if not isinstance(data, dict):
            logger.error("Unrecognized CLOB order book response for %s", token_id)
            return None

        return OrderBook(
            token_id=token_id,
            timestamp=time.time(),
            bids=[
                OrderBookLevel(
                    price=_parse_float(level.get("price")),
                    size=_parse_float(level.get("size")),
                )
                for level in data.get("bids", data.get("buys", []))
                if isinstance(level, dict)
            ],
            asks=[
                OrderBookLevel(
                    price=_parse_float(level.get("price")),
                    size=_parse_float(level.get("size")),
                )
                for level in data.get("asks", data.get("sells", []))
                if isinstance(level, dict)
            ],
        )

    async def close(self) -> None:
        await self.client.close()
