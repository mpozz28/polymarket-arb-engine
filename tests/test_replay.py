import json

import pytest

from src.backtest.replay import JsonlReplayFeed


def _event(timestamp: float, closed: bool = False) -> dict:
    return {
        "timestamp": timestamp,
        "market": {
            "condition_id": "mkt_1",
            "question": "Event?",
            "tokens": [
                {"token_id": "Y", "outcome": "Yes"},
                {"token_id": "N", "outcome": "No"},
            ],
            "active": not closed,
            "closed": closed,
        },
        "order_books": {
            "Y": {
                "token_id": "Y",
                "timestamp": timestamp,
                "bids": [],
                "asks": [{"price": 0.40, "size": 10}],
            },
            "N": {
                "token_id": "N",
                "timestamp": timestamp,
                "bids": [],
                "asks": [{"price": 0.50, "size": 10}],
            },
        },
    }


def test_jsonl_replay_feed_round_trip(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        json.dumps(_event(100.0)) + "\n" + json.dumps(_event(101.0, closed=True)) + "\n",
        encoding="utf-8",
    )

    events = list(JsonlReplayFeed(path))
    assert len(events) == 2
    assert events[0][0] == 100.0
    assert events[0][1].condition_id == "mkt_1"
    assert events[0][2]["Y"].best_ask == 0.40
    assert events[1][1].closed


def test_jsonl_replay_normalizes_real_millisecond_timestamp(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(json.dumps(_event(1_710_000_000_000)) + "\n", encoding="utf-8")

    events = list(JsonlReplayFeed(path))
    assert events[0][0] == pytest.approx(1_710_000_000.0)


def test_jsonl_replay_rejects_out_of_order_events(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text(
        json.dumps(_event(101.0)) + "\n" + json.dumps(_event(100.0)) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="non-decreasing"):
        list(JsonlReplayFeed(path))
