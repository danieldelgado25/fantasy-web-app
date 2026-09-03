"""
test_projection_service.py
===========================
Focused unit tests for the "as of" row selection logic — the trickiest, most
bug-prone part of projection_service.py (getting the target-week filtering
wrong would silently leak future data into projections). These use small
synthetic polars DataFrames rather than the real pipeline, so they run fast
and don't require network access to nflreadpy.

Run with: pytest tests/ (from backend/)
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import polars as pl
import pytest

from wr_webapp.services.projection_service import _select_as_of_rows


def _synthetic_weekly() -> pl.DataFrame:
    """Two players, a few weeks each, with rolling_3 columns so the
    non-null-rolling-3 filter in _select_as_of_rows has something to check."""
    return pl.DataFrame({
        "player_id": ["P1", "P1", "P1", "P2", "P2", "P2"],
        "season": [2024, 2024, 2024, 2024, 2024, 2024],
        "week": [3, 4, 5, 3, 4, 5],
        "season_type": ["REG"] * 6,
        "team": ["NYG", "NYG", "NYG", "SF", "SF", "SF"],
        "ppr_points_rolling_3": [None, 8.0, 9.5, None, 10.0, 11.0],
    })


def test_select_as_of_rows_picks_most_recent_prior_week():
    """For target week 6, each player's row should be their latest week < 6."""
    weekly = _synthetic_weekly()
    result = _select_as_of_rows(weekly, target_season=2024, target_week=6)

    rows = {r["player_id"]: r["week"] for r in result.to_dicts()}
    assert rows["P1"] == 5
    assert rows["P2"] == 5


def test_select_as_of_rows_excludes_current_and_future_weeks():
    """Projecting week 5 should never use week 5's own stats as input —
    that would be the exact data leakage the notebook's docs warn against."""
    weekly = _synthetic_weekly()
    result = _select_as_of_rows(weekly, target_season=2024, target_week=5)

    rows = {r["player_id"]: r["week"] for r in result.to_dicts()}
    assert rows["P1"] == 4  # not 5 — week 5 hasn't happened yet relative to this target
    assert rows["P2"] == 4


def test_select_as_of_rows_drops_null_rolling_features():
    """A player whose only prior row has a null rolling_3 (not enough history
    yet) should be excluded rather than handed to the model with missing
    features it wasn't trained to expect at inference time this way."""
    weekly = pl.DataFrame({
        "player_id": ["ROOKIE"],
        "season": [2024],
        "week": [1],
        "season_type": ["REG"],
        "team": ["KC"],
        "ppr_points_rolling_3": [None],
    })
    result = _select_as_of_rows(weekly, target_season=2024, target_week=2)
    assert result.is_empty()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
