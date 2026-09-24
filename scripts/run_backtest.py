import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.backtest.engine import BacktestEngine
from src.backtest.replay import JsonlReplayFeed
from src.backtest.report import export_backtest
from src.detectors.structural import IntraMarketArbDetector
from src.pricing.execution import PricingEngine
from src.risk.manager import RiskManager


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a deterministic Polymarket replay backtest")
    parser.add_argument(
        "replay_file",
        nargs="?",
        default=str(ROOT / "examples" / "replay_sample.jsonl"),
        help="Path to a JSONL replay file",
    )
    parser.add_argument("--capital", type=float, default=10_000.0)
    parser.add_argument("--threshold", type=float, default=0.99)
    parser.add_argument("--fee-rate", type=float, default=0.0)
    parser.add_argument("--win-probability", type=float, default=0.99)
    parser.add_argument("--max-exposure", type=float, default=0.05)
    parser.add_argument("--kelly-multiplier", type=float, default=0.5)
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional directory for summary.json, trades.csv and equity_curve.csv",
    )
    args = parser.parse_args()

    if args.capital <= 0:
        raise SystemExit("--capital must be greater than zero")
    if not 0.0 < args.threshold <= 1.0:
        raise SystemExit("--threshold must be in (0, 1]")
    if args.fee_rate < 0:
        raise SystemExit("--fee-rate must be >= 0")
    if not 0.0 <= args.win_probability <= 1.0:
        raise SystemExit("--win-probability must be in [0, 1]")
    if not 0.0 < args.max_exposure <= 1.0:
        raise SystemExit("--max-exposure must be in (0, 1]")
    if not 0.0 <= args.kelly_multiplier <= 1.0:
        raise SystemExit("--kelly-multiplier must be in [0, 1]")

    detector = IntraMarketArbDetector(
        PricingEngine(taker_fee_rate=args.fee_rate),
        max_cost_threshold=args.threshold,
    )
    engine = BacktestEngine(
        initial_capital=args.capital,
        detectors=[detector],
        risk_manager=RiskManager(assumed_win_probability=args.win_probability),
        max_exposure_per_trade=args.max_exposure,
        fractional_kelly_multiplier=args.kelly_multiplier,
    )
    engine.run(JsonlReplayFeed(args.replay_file))

    result = {
        "replay_file": str(Path(args.replay_file).resolve()),
        "metrics": engine.summary(),
    }

    if args.output_dir:
        result["artifacts"] = export_backtest(engine, args.output_dir)

    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
