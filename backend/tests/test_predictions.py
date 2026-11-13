from datetime import datetime

import polars as pl

from wr_predictor import features, predictions
from wr_predictor.predictions import add_rank, check_gate, not_yet_kicked_off, season_points, upsert_log

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


def test_changed_after_kickoff_flags_only_games_that_had_started() -> None:
    old = pl.DataFrame({"season": [2026] * 3, "week": [9] * 3, "player_id": ["A", "B", "C"], "team": ["SEA", "SF", "SEA"], "pred": [1.0, 2.0, 3.0]})
    # A and B edited, C removed, D added. SEA kicked off at 13:00; SF plays at 20:20.
    new = pl.DataFrame({"season": [2026] * 3, "week": [9] * 3, "player_id": ["A", "B", "D"], "team": ["SEA", "SF", "SEA"], "pred": [9.0, 9.0, 4.0]})
    schedule = pl.DataFrame(
        {"season": [2026, 2026], "week": [9, 9], "team": ["SEA", "SF"], "gameday": ["2026-11-08"] * 2, "gametime": ["13:00", "20:20"]}
    )

    result = predictions.changed_after_kickoff(old, new, schedule, datetime(2026, 11, 8, 13, 30))

    # B's game hadn't started, so editing it is allowed; every SEA change is not.
    assert result["player_id"].to_list() == ["A", "C", "D"]


def test_changed_after_kickoff_is_empty_when_nothing_changed() -> None:
    log = pl.DataFrame({"season": [2026], "week": [9], "player_id": ["A"], "team": ["SEA"], "pred": [None]})
    schedule = pl.DataFrame({"season": [2026], "week": [9], "team": ["SEA"], "gameday": ["2026-11-08"], "gametime": ["13:00"]})

    # A null value must still count as unchanged.
    assert predictions.changed_after_kickoff(log, log, schedule, datetime(2026, 11, 9)).is_empty()


def test_live_weeks_only_skips_the_partly_logged_first_week() -> None:
    log = pl.DataFrame({"week": [8, 9, 10]})

    # 2026 logging began partway through week 8; other seasons count from week 1.
    assert predictions.live_weeks_only(log, 2026)["week"].to_list() == [9, 10]
    assert predictions.live_weeks_only(log, 2027)["week"].to_list() == [8, 9, 10]


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


def _score(
    week: int,
    mae: float = 5.0,
    baseline_mae: float = 6.0,
    correlation: float = 0.2,
    baseline_correlation: float = 0.1,
    predicted: int = 20,
) -> dict:
    """Build one week's score with passing values unless a test overrides them."""
    return {
        "week": week,
        "predicted": predicted,
        "played": 18,
        "ppr_points_mae": mae,
        "ppr_points_baseline_mae": baseline_mae,
        "rank_correlation": correlation,
        "baseline_rank_correlation": baseline_correlation,
    }


def test_check_gate_passes_with_four_good_finished_weeks() -> None:
    gate = check_gate([_score(w) for w in (1, 2, 3, 4)], completed_weeks=[1, 2, 3, 4])

    assert gate["passed"] is True
    assert gate["weeks"] == [1, 2, 3, 4]


def test_check_gate_needs_enough_finished_weeks() -> None:
    # Week 4 isn't finished, so only three weeks qualify.
    gate = check_gate([_score(w) for w in (1, 2, 3, 4)], completed_weeks=[1, 2, 3])

    assert gate["passed"] is False
    assert "has 3" in gate["reason"]


def test_check_gate_fails_each_check_independently() -> None:
    weeks = [1, 2, 3, 4]

    assert check_gate([_score(w, mae=7.0) for w in weeks], weeks)["beats_baseline"] is False
    assert check_gate([_score(w, correlation=0.05) for w in weeks], weeks)["ranks_better_than_baseline"] is False
    assert check_gate([_score(w, predicted=19) for w in weeks], weeks)["all_predictions_made"] is False


def test_add_rank_breaks_ties_the_same_way_regardless_of_input_order() -> None:
    points = pl.DataFrame({"player_id": ["A", "B"], "season_points": [50.0, 50.0]})

    first = add_rank(pl.DataFrame({"player_id": ["A", "B"]}), points)
    second = add_rank(pl.DataFrame({"player_id": ["B", "A"]}), points)

    assert first.sort("player_id")["rank"].to_list() == second.sort("player_id")["rank"].to_list()


def test_summarize_accuracy_keeps_finished_weeks_and_replaces_undefined_values() -> None:
    finished = _score(1, baseline_correlation=float("nan"))
    unfinished = _score(2)

    summary = predictions.summarize_accuracy([finished, unfinished], {"passed": False, "reason": "too few"}, completed_weeks=[1])

    assert [week["week"] for week in summary["weeks"]] == [1]
    # A NaN would make the JSON file unreadable in the browser.
    assert summary["weeks"][0]["baseline_rank_correlation"] is None
    assert summary["reason"] == "too few"


def test_build_review_shows_differences_and_keeps_players_who_did_not_play() -> None:
    log = pl.DataFrame(
        {
            "season": [2026, 2026],
            "week": [5, 5],
            "player_id": ["A", "B"],
            "player_name": ["Player A", "Player B"],
            "team": ["SEA", "DAL"],
            "opponent_team": ["NE", "NYG"],
            "season_points": [90.0, 80.0],
            **{f"pred_{s}": [10.0, 5.0] for s in predictions.REVIEW_STATS},
        }
    )
    actuals = pl.DataFrame({"season": [2026], "week": [5], "player_id": ["A"], **{s: [12.5] for s in predictions.REVIEW_STATS}})

    review = predictions.build_review(log, actuals).sort("player_name")

    # A beat the projection by 2.5; B didn't play, so has no actual or difference.
    assert review["diff_ppr_points"].to_list() == [2.5, None]
    assert review["actual_targets"].to_list() == [12.5, None]


def test_score_predictions_scores_top_players_only_and_counts_who_played(monkeypatch) -> None:
    monkeypatch.setattr(predictions, "TOP_N", 2)
    log = pl.DataFrame(
        {
            "season": [2026] * 3,
            "week": [5] * 3,
            "player_id": ["A", "B", "C"],
            "season_points": [90.0, 80.0, 10.0],
            **{f"pred_{s}": [10.0, 5.0, 1.0] for s in predictions.PREDICTED_STATS},
            **{f"base_{s}": [8.0, 8.0, 1.0] for s in predictions.PREDICTED_STATS},
        }
    )
    # C is outside the top players and has no effect; B's actual is off by 1, A's by 2.
    actuals = pl.DataFrame(
        {
            "season": [2026] * 3,
            "week": [5] * 3,
            "player_id": ["A", "B", "C"],
            **{s: [12.0, 4.0, 500.0] for s in predictions.PREDICTED_STATS},
        }
    )

    score = predictions.score_predictions(log, actuals)[0]

    assert score["predicted"] == 2
    assert score["ppr_points_mae"] == 1.5
    assert score["ppr_points_baseline_mae"] == 4.0
    assert score["rank_correlation"] == 1.0
    assert score["baseline_rank_correlation"] is not None


def test_build_player_history_prefers_live_flags_replay_and_keeps_missed_games() -> None:
    def log(weeks: list[int], points: list[float]) -> pl.DataFrame:
        return pl.DataFrame({"season": [2026] * len(weeks), "week": weeks, "player_id": ["A"] * len(weeks), "pred_ppr_points": points})

    live = log([8, 9], [20.0, 15.0])
    # Replay covers weeks 7-8 and a week 10 that hasn't finished.
    replay = log([7, 8, 10], [10.0, 99.0, 5.0])
    actuals = pl.DataFrame({"season": [2026, 2026], "week": [7, 8], "player_id": ["A", "A"], "ppr_points": [12.5, 18.0]})

    history = predictions.build_player_history(live, replay, actuals, [7, 8, 9], ["A", "Z"])

    # Week 8 uses live, not the replay's 99; week 9 has no actual because A didn't play; week 10 isn't finished.
    assert history == {
        "A": [
            {"week": 7, "projected": 10.0, "actual": 12.5, "diff": 2.5, "tier": "Solid", "replay": True},
            {"week": 8, "projected": 20.0, "actual": 18.0, "diff": -2.0, "tier": "Strong", "replay": False},
            {"week": 9, "projected": 15.0, "actual": None, "diff": None, "tier": None, "replay": False},
        ]
    }


def test_game_tier_uses_each_floor_inclusively_and_skips_missed_games() -> None:
    points = pl.DataFrame({"p": [None, 0.0, 4.99, 5.0, 10.0, 15.0, 20.0, 30.0, 45.0]})

    tiers = points.select(predictions.game_tier(pl.col("p")).alias("tier"))["tier"].to_list()

    assert tiers == [None, "Dud", "Dud", "Low", "Solid", "Strong", "Boom", "NUCLEAR", "NUCLEAR"]
