import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)


class PolymarketWSClient:
    def __init__(
        self,
        token_ids: list[str],
        on_message_callback: Callable[[dict], Awaitable[None]],
        heartbeat_interval_seconds: float = 10.0,
        subscription_chunk_size: int = 100,
    ):
        self.ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        self.token_ids = token_ids
        self.on_message_callback = on_message_callback
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.subscription_chunk_size = subscription_chunk_size
        self.is_running = False

    async def _heartbeat(self, websocket) -> None:
        while self.is_running:
            await asyncio.sleep(self.heartbeat_interval_seconds)
            await websocket.send("PING")

    async def start(self) -> None:
        self.is_running = True
        reconnect_delay = 1.0

        while self.is_running:
            heartbeat_task = None
            try:
                logger.info("Connecting to %s", self.ws_url)

                async with websockets.connect(
                    self.ws_url,
                    max_size=None,
                    ping_interval=None,
                ) as websocket:
                    for start in range(0, len(self.token_ids), self.subscription_chunk_size):
                        chunk = self.token_ids[start : start + self.subscription_chunk_size]
                        subscription = {
                            "assets_ids": chunk,
                            "type": "market",
                            "custom_feature_enabled": True,
                        }
                        await websocket.send(json.dumps(subscription))
                        await asyncio.sleep(0.1)

                    logger.info("Subscribed to %d market assets", len(self.token_ids))
                    heartbeat_task = asyncio.create_task(self._heartbeat(websocket))
                    reconnect_delay = 1.0

                    async for message in websocket:
                        if not message:
                            continue
                        if isinstance(message, str) and message.strip().upper() == "PONG":
                            continue

                        try:
                            data = json.loads(message)
                        except (TypeError, json.JSONDecodeError):
                            logger.debug("Ignoring non-JSON WebSocket frame: %r", message)
                            continue

                        if not isinstance(data, (dict, list)):
                            continue

                        try:
                            if isinstance(data, list):
                                for item in data:
                                    if isinstance(item, dict):
                                        await self.on_message_callback(item)
                            else:
                                await self.on_message_callback(data)
                        except Exception:
                            logger.exception("Market event callback failed")

            except asyncio.CancelledError:
                raise
            except (ConnectionClosed, ConnectionError, TimeoutError, ValueError, OSError) as exc:
                if self.is_running:
                    logger.warning(
                        "WebSocket disconnected (%s); reconnecting in %.1fs",
                        exc,
                        reconnect_delay,
                    )
                    await asyncio.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2.0, 30.0)
            finally:
                if heartbeat_task is not None:
                    heartbeat_task.cancel()
                    try:
                        await heartbeat_task
                    except asyncio.CancelledError:
                        pass

    async def stop(self) -> None:
        self.is_running = False
