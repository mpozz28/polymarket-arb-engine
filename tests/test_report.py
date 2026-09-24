import json

from src.backtest.engine import BacktestEngine
from src.backtest.report import export_backtest


def test_export_backtest_writes_machine_readable_artifacts(tmp_path):
    engine = BacktestEngine(
        initial_capital=100.0,
        detectors=[],
        risk_manager=None,
    )  # type: ignore[arg-type]
    paths = export_backtest(engine, tmp_path)

    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert summary["total_trades"] == 0
    assert set(paths) == {"summary", "trades", "equity_curve"}
    assert (tmp_path / "trades.csv").read_text(encoding="utf-8").startswith("timestamp,")
    assert (tmp_path / "equity_curve.csv").read_text(encoding="utf-8").startswith("timestamp,")
