import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.websocket import PolymarketWSClient

logger = logging.getLogger(__name__)


class JsonlCapture:
    def __init__(self, output_path: Path) -> None:
        self.output_path = output_path
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.output_path.open("a", encoding="utf-8")
        self.count = 0

    async def on_message(self, message: dict[str, Any]) -> None:
        record = {
            "captured_at": time.time(),
            "event": message,
        }
        self.handle.write(json.dumps(record, separators=(",", ":")) + "\n")
        self.handle.flush()
        self.count += 1

    def close(self) -> None:
        self.handle.close()


async def run(token_ids: list[str], output: Path, duration: float) -> int:
    capture = JsonlCapture(output)
    client = PolymarketWSClient(token_ids=token_ids, on_message_callback=capture.on_message)
    task = asyncio.create_task(client.start())

    try:
        await asyncio.sleep(duration)
    finally:
        await client.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        capture.close()

    return capture.count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture public Polymarket market-channel events into JSONL"
    )
    parser.add_argument(
        "--token-id",
        action="append",
        required=True,
        help="Token/asset ID to subscribe to. Repeat for multiple tokens.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Output JSONL path")
    parser.add_argument("--duration", type=float, default=60.0, help="Capture duration in seconds")
    args = parser.parse_args()

    token_ids = [token.strip() for token in args.token_id if token.strip()]
    if not token_ids:
        raise SystemExit("At least one non-empty --token-id is required")
    if args.duration <= 0:
        raise SystemExit("--duration must be greater than zero")

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    count = asyncio.run(run(token_ids, args.output, args.duration))
    print(json.dumps({"output": str(args.output.resolve()), "events_captured": count}, indent=2))


if __name__ == "__main__":
    main()
