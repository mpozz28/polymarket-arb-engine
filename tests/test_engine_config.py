import pytest

from src.backtest.engine import BacktestEngine


def test_engine_accepts_configurable_risk_parameters():
    engine = BacktestEngine(
        initial_capital=100.0,
        detectors=[],
        risk_manager=None,  # type: ignore[arg-type]
        max_exposure_per_trade=0.20,
        fractional_kelly_multiplier=0.25,
    )
    assert engine.portfolio.max_exposure_per_trade == 0.20
    assert engine.portfolio.fractional_kelly_multiplier == 0.25


@pytest.mark.parametrize("kwargs", [
    {"max_exposure_per_trade": 0.0},
    {"max_exposure_per_trade": 1.1},
    {"fractional_kelly_multiplier": -0.1},
    {"fractional_kelly_multiplier": 1.1},
])
def test_engine_rejects_invalid_risk_parameters(kwargs):
    with pytest.raises(ValueError):
        BacktestEngine(
            initial_capital=100.0,
            detectors=[],
            risk_manager=None,
            **kwargs,
        )  # type: ignore[arg-type]
