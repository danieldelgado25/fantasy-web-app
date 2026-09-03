import polars as pl

from src.wr_predictor import data_loader
from src.wr_predictor.dataset_builder import (
    _find_first_existing,
    _merge_ff_opportunity,
    _merge_schedule_context,
    _normalize_receiving_columns,
    build_training_dataset,
)


"""
Uses Pytest to verify dataset_builder.py: the pure column-name helpers,
the schedule/ff_opportunity merge steps, and the build_training_dataset
orchestration. data_loader calls are monkeypatched so no real nflreadpy/
network call is made.
"""


def test_normalize_receiving_columns_renames_nflreadpy_names() -> None:
    data_frame = pl.DataFrame(
        {"receptions": [5], "receiving_yards": [80], "receiving_tds": [1]}
    )

    result = _normalize_receiving_columns(data_frame)

    assert set(result.columns) == {"rec", "rec_yds", "rec_td"}


def test_normalize_receiving_columns_skips_when_already_present() -> None:
    data_frame = pl.DataFrame({"receptions": [5], "rec": [5]})

    result = _normalize_receiving_columns(data_frame)

    # Both columns survive untouched; renaming would have collided with "rec".
    assert set(result.columns) == {"receptions", "rec"}


def test_find_first_existing_returns_first_match() -> None:
    assert _find_first_existing(["gsis_id", "player_id"], ["player_id", "gsis_id"]) == "player_id"


def test_find_first_existing_returns_none_when_no_match() -> None:
    assert _find_first_existing(["foo"], ["player_id", "gsis_id"]) is None


def test_merge_schedule_context_adds_situational_columns(monkeypatch) -> None:
    weekly = pl.DataFrame({"game_id": ["g1", "g1", "g2"], "team": ["KC", "SF", "KC"]})
    schedules = pl.DataFrame(
        {
            "game_id": ["g1", "g2"],
            "home_team": ["KC", "DAL"],
            "away_team": ["SF", "KC"],
            "spread_line": [-3.0, 2.5],
            "total_line": [48.5, 44.0],
            "roof": ["outdoors", "dome"],
        }
    )
    monkeypatch.setattr(data_loader, "load_schedules", lambda seasons: schedules)

    result = _merge_schedule_context(weekly, [2024])

    assert result["is_home"].to_list() == [1, 0, 0]
    assert result["is_dome"].to_list() == [0, 0, 1]
    assert result["spread_line"].to_list() == [-3.0, -3.0, 2.5]


def test_merge_schedule_context_passthrough_without_game_id(monkeypatch) -> None:
    weekly = pl.DataFrame({"team": ["KC"]})

    def load_schedules(seasons):
        raise AssertionError("load_schedules should not be called without game_id")

    monkeypatch.setattr(data_loader, "load_schedules", load_schedules)

    result = _merge_schedule_context(weekly, [2024])

    assert result.equals(weekly)


def test_merge_ff_opportunity_joins_preferred_numeric_columns(monkeypatch) -> None:
    weekly = pl.DataFrame({"player_id": ["A", "B"], "season": [2024, 2024], "week": [1, 1]})
    ff = pl.DataFrame(
        {
            "player_id": ["A", "B"],
            "season": [2024, 2024],
            "week": [1, 1],
            "expected_yards": [55.0, 30.0],
            "fantasy_points_exp": [12.0, 8.0],
            "other_numeric": [1, 2],
            "note": ["x", "y"],
        }
    )
    monkeypatch.setattr(data_loader, "load_ff_opportunity", lambda seasons: ff)

    result, extra_cols = _merge_ff_opportunity(weekly, [2024])

    assert extra_cols == ["expected_yards", "fantasy_points_exp"]
    assert "other_numeric" not in result.columns
    assert result["expected_yards"].to_list() == [55.0, 30.0]


def test_merge_ff_opportunity_passthrough_when_join_keys_missing(monkeypatch) -> None:
    weekly = pl.DataFrame({"player_id": ["A"], "season": [2024]})  # no "week"
    ff = pl.DataFrame({"player_id": ["A"], "season": [2024], "week": [1], "expected_yards": [55.0]})
    monkeypatch.setattr(data_loader, "load_ff_opportunity", lambda seasons: ff)

    result, extra_cols = _merge_ff_opportunity(weekly, [2024])

    assert extra_cols == []
    assert result.equals(weekly)


def test_build_training_dataset_orchestrates_pipeline(monkeypatch, tmp_path) -> None:
    # Player A: 5 games in-season (survives default min_games_for_player=4).
    # Player B: 2 games (dropped by the min-games filter).
    weekly = pl.DataFrame(
        {
            "player_id": ["A"] * 5 + ["B"] * 2,
            "season": [2024] * 7,
            "week": [1, 2, 3, 4, 5, 1, 2],
            "position": ["WR"] * 7,
            "rec": [5, 6, 7, 8, 9, 3, 4],
            "rec_yds": [50, 60, 70, 80, 90, 30, 40],
            "rec_td": [0, 1, 0, 1, 0, 0, 0],
            "targets": [7, 8, 9, 10, 11, 5, 6],
        }
    )
    monkeypatch.setattr(data_loader, "load_player_weekly_stats", lambda seasons: weekly)
    monkeypatch.setattr(data_loader, "load_players", lambda: pl.DataFrame())

    output_path = str(tmp_path / "out.csv")
    result = build_training_dataset(seasons=[2024], output_path=output_path)

    # Only player A survives: min-games filter drops B, and each player's
    # final week is dropped for lacking a next-week target.
    assert result.height == 4
    assert set(result["player_id"].to_list()) == {"A"}
    assert "next_week_ppr_points" in result.columns
    assert result["ppr_points"].to_list()[0] == 10.0  # 5*1 + 50*0.1 + 0*6
    assert (tmp_path / "out.csv").exists()
