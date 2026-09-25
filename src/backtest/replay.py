import json
from collections.abc import Iterator
from pathlib import Path

from src.core.models import Market, OrderBook


class JsonlReplayFeed:
    """Replay timestamped market/order-book snapshots from a JSONL file.

    Each line must contain:
      {
        "timestamp": 1710000000.0,
        "market": { ... Market fields ... },
        "order_books": {
          "token_id": { ... OrderBook fields ... }
        }
      }

    Timestamps are normalized from milliseconds to seconds when they are large
    Unix timestamps. The feed rejects out-of-order events to make replay
    semantics explicit and reproducible.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def __iter__(self) -> Iterator[tuple[float, Market, dict[str, OrderBook]]]:
        previous_timestamp = float("-inf")

        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue

                try:
                    payload = json.loads(line)
                    timestamp = _normalize_timestamp(payload["timestamp"])
                    market = Market.model_validate(payload["market"])
                    raw_books = payload["order_books"]
                    order_books = {
                        str(token_id): OrderBook.model_validate(book)
                        for token_id, book in raw_books.items()
                    }
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(
                        f"Invalid replay event on line {line_number} of {self.path}: {exc}"
                    ) from exc

                if timestamp < previous_timestamp:
                    raise ValueError(
                        f"Replay timestamps must be non-decreasing: line {line_number} "
                        f"has {timestamp}, previous event was {previous_timestamp}"
                    )

                previous_timestamp = timestamp
                yield timestamp, market, order_books


def _normalize_timestamp(value: object) -> float:
    timestamp = float(value)
    return timestamp / 1000.0 if timestamp >= 100_000_000_000 else timestamp
