# Public market-data capture

`capture_market_data.py` records raw events from the public Polymarket market WebSocket into append-only JSONL. It is intended to build a small reproducible dataset for later replay/backtesting.

## Example

```bash
python scripts/capture_market_data.py \
  --token-id <TOKEN_ID_YES> \
  --token-id <TOKEN_ID_NO> \
  --duration 300 \
  --output data/raw/session_01.jsonl
```

The recorder stores the local capture timestamp plus the original WebSocket event. It does not submit orders or require trading credentials.

The raw capture is deliberately separate from `src/backtest/replay.py`: converting raw market events into a normalized backtest feed is a distinct data-engineering step that should preserve the event timestamps and avoid lookahead.

`data/raw/` and generated captures are ignored by Git so credentials, large datasets and local experiment artifacts are not accidentally committed.
