from datetime import datetime

import polars as pl

from wr_predictor import features
from wr_predictor.predictions import add_rank, not_yet_kicked_off, season_points, upsert_log

"""
Uses Pytest to verify the prediction log and scoring rules, plus the rolling
averages the baseline depends on. All data is hand-written, so no network is used.
"""


def test_rolling_average_includes_latest_game_but_not_the_next() -> None:
    weekly = pl.DataFrame({"player_id": ["A"] * 3, "season": [2026] * 3, "week": [1, 2, 3], "ppr_points": [10.0, 20.0, 90.0]})

    result = features.add_rolling_features(features.add_lag_features(weekly))

    # Week 2's row is used to predict week 3, so it can see weeks 1-2 but never week 3's 90.
    assert result["ppr_points_rolling_3"].to_list() == [10.0, 15.0, 40.0]


def test_official_points_are_preferred_over_receiving_only_formula() -> None:
    # 5 catches and 50 yards would be 10.0 by the formula; official includes rushing.
    data_frame = pl.DataFrame({"rec": [5], "rec_yds": [50], "rec_td": [0], "fantasy_points_ppr": [14.2]})

    assert features.add_basic_fantasy_points(data_frame)["ppr_points"].to_list() == [14.2]


def test_season_points_falls_back_to_previous_season_before_games_are_played() -> None:
    stats = pl.DataFrame(
        {"player_id": ["A", "A"], "season": [2025, 2025], "season_type": ["REG", "POST"], "fantasy_points_ppr": [10.0, 99.0]}
    )

    # Playoff points don't count toward the ranking.
    assert season_points(stats, 2026)["season_points"].to_list() == [10.0]


def test_add_rank_orders_best_first_and_puts_players_without_points_last() -> None:
    frame = pl.DataFrame({"player_id": ["A", "B", "C"]})
    points = pl.DataFrame({"player_id": ["A", "B"], "season_points": [50.0, 80.0]})

    result = add_rank(frame, points).sort("player_id")

    assert result["rank"].to_list() == [2, 1, 3]


def test_not_yet_kicked_off_uses_time_and_keeps_unknown_times() -> None:
    frame = pl.DataFrame(
        {
            "player_id": ["started", "later", "unknown"],
            "gameday": ["2026-11-08", "2026-11-08", "2026-11-08"],
            "gametime": ["13:00", "20:20", None],
        }
    )

    result = not_yet_kicked_off(frame, datetime(2026, 11, 8, 13, 30))

    assert result["player_id"].to_list() == ["later", "unknown"]


def test_upsert_log_replaces_same_game_and_keeps_other_rows(tmp_path) -> None:
    path = str(tmp_path / "predictions" / "2026.csv")
    upsert_log(path, pl.DataFrame({"season": [2026, 2026], "week": [8, 9], "player_id": ["A", "A"], "pred_ppr_points": [10.0, 11.0]}))

    # Week 8 kicked off, so it isn't passed again; week 9 is refreshed.
    result = upsert_log(path, pl.DataFrame({"season": [2026], "week": [9], "player_id": ["A"], "pred_ppr_points": [12.0]}))

    assert result["pred_ppr_points"].to_list() == [10.0, 12.0]


def test_add_rank_breaks_ties_the_same_way_regardless_of_input_order() -> None:
    points = pl.DataFrame({"player_id": ["A", "B"], "season_points": [50.0, 50.0]})

    first = add_rank(pl.DataFrame({"player_id": ["A", "B"]}), points)
    second = add_rank(pl.DataFrame({"player_id": ["B", "A"]}), points)

    assert first.sort("player_id")["rank"].to_list() == second.sort("player_id")["rank"].to_list()
