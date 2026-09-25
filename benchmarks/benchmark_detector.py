import argparse
import json
import platform
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.models import Market, OrderBook, OrderBookLevel, Token
from src.detectors.structural import IntraMarketArbDetector
from src.pricing.execution import PricingEngine


def build_fixture() -> tuple[Market, dict[str, OrderBook]]:
    market = Market(
        condition_id="benchmark-market",
        question="Synthetic benchmark event",
        tokens=[Token(token_id="Y", outcome="Yes"), Token(token_id="N", outcome="No")],
        active=True,
        closed=False,
    )
    books = {
        "Y": OrderBook(
            token_id="Y",
            timestamp=1_000.0,
            bids=[OrderBookLevel(price=0.39, size=100.0)],
            asks=[
                OrderBookLevel(price=0.40, size=100.0),
                OrderBookLevel(price=0.41, size=100.0),
            ],
        ),
        "N": OrderBook(
            token_id="N",
            timestamp=1_000.0,
            bids=[OrderBookLevel(price=0.49, size=100.0)],
            asks=[OrderBookLevel(price=0.50, size=100.0), OrderBookLevel(price=0.51, size=100.0)],
        ),
    }
    return market, books


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark detector time on a fixed synthetic order book"
    )
    parser.add_argument("--iterations", type=int, default=5_000)
    parser.add_argument("--warmup", type=int, default=250)
    args = parser.parse_args()
    if args.iterations <= 0 or args.warmup < 0:
        raise SystemExit("iterations must be > 0 and warmup must be >= 0")

    detector = IntraMarketArbDetector(PricingEngine(taker_fee_rate=0.0), max_cost_threshold=0.99)
    market, books = build_fixture()
    for _ in range(args.warmup):
        detector.detect(market, books)

    samples_ms = []
    opportunities = 0
    for _ in range(args.iterations):
        start = time.perf_counter()
        found = detector.detect(market, books)
        samples_ms.append((time.perf_counter() - start) * 1_000)
        opportunities += len(found)

    samples_ms.sort()
    p95_index = min(len(samples_ms) - 1, int(len(samples_ms) * 0.95))
    print(json.dumps({
        "iterations": args.iterations,
        "warmup": args.warmup,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "opportunities_per_iteration": opportunities / args.iterations,
        "mean_ms": statistics.fmean(samples_ms),
        "median_ms": statistics.median(samples_ms),
        "p95_ms": samples_ms[p95_index],
        "min_ms": samples_ms[0],
        "max_ms": samples_ms[-1],
        "scope": "detector computation only on a fixed synthetic order book",
    }, indent=2))


if __name__ == "__main__":
    main()
