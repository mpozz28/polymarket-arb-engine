# Backtest methodology

This repository separates software validation from historical performance evidence.

## Replay

`JsonlReplayFeed` reads timestamped JSONL snapshots. Events must be ordered by non-decreasing timestamp; large Unix timestamps expressed in milliseconds are normalized to seconds.

The included `examples/replay_sample.jsonl` is a **synthetic deterministic fixture**. It validates the event loop, risk limits, settlement accounting, equity tracking, and metrics. It is not historical Polymarket data and is not evidence of real-world profitability.

## Trade accounting

An approved binary structural-arbitrage trade locks the detector-approved capital. At settlement, the simulated payout is one dollar per matched share. Realized PnL is `expected_payout - capital_invested`. This assumes the detector's quoted size was executable and does not model queue position, cancellations, partial fills after entry, settlement disputes, or exchange downtime.

## Metrics

Trade-level metrics include PnL, return on invested capital, win rate, average trade PnL, gross profit/loss, profit factor, and average trade ROI. Portfolio-level metrics include total return and max drawdown from the recorded equity curve.

Return on invested capital and portfolio return are intentionally different: a trade can earn a high percentage on the capital committed while the portfolio moves by a much smaller percentage when exposure is capped.

`profit_factor` is `null` when there are no losing trades because the ratio is undefined in that sample. This keeps the command-line output valid strict JSON.

## Reproducibility

Run the deterministic fixture:

```bash
python scripts/run_backtest.py
```

Run the local detector benchmark:

```bash
python benchmarks/benchmark_detector.py --iterations 5000
```

Benchmark results depend on hardware, Python version, and system load. They measure local detector computation only; they are not network latency measurements or HFT performance claims.

## Reproducible outputs

The backtest runner accepts explicit strategy and risk parameters so the replay can be rerun with a different configuration without editing source code. Use `--output-dir` to export `summary.json`, `trades.csv` and `equity_curve.csv`.

Example:

```bash
python scripts/run_backtest.py --capital 10000 --threshold 0.99 --fee-rate 0.0 --win-probability 0.99 --max-exposure 0.05 --kelly-multiplier 0.5 --output-dir artifacts/example
```

These parameters describe the simulation assumptions; they are not calibrated estimates of future trading performance.
