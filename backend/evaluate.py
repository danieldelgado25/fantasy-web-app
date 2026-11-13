from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

import nflreadpy as nfl
import polars as pl

from train import FIRST_TRAIN_SEASON
from wr_predictor import data_loader
from wr_predictor.dataset_builder import _normalize_receiving_columns, build_latest_snapshot, build_training_dataset, team_game_context
from wr_predictor.model import (
    get_feature_columns,
    get_rushing_feature_columns,
    predict_stats,
    prepare_inference_frame,
    prepare_model_frame,
    train_stat_models,
)
from wr_predictor.predictions import (
    add_rank,
    build_log_rows,
    build_player_history,
    build_review,
    check_gate,
    live_weeks_only,
    score_predictions,
    season_points,
    summarize_accuracy,
    TOP_N,
)
from wr_predictor.stats import NEXT_GAME_CONTEXT, POINTS_STAT, PREDICTED_STATS

"""
Scores saved predictions against actual results and writes a report.
Run from backend/: python evaluate.py
Add --replay to first regenerate this season's past weeks into a separate file, using
only games before each week. Replays are for testing the model today; only the
live log proves predictions were made ahead of time.
"""

PREDICTIONS_DIR = "predictions"

# Served as a static file by the frontend.
ACCURACY_PATH = "../frontend/public/data/accuracy.json"
# Each player's weekly projected vs actual points, for the site's tracker.
HISTORY_PATH = "../frontend/public/data/player_history.json"
# Written by train.py, which the daily job runs first; decides whose history is published.
PROJECTIONS_PATH = "../frontend/public/data/projections.json"


def load_actuals(stats: pl.DataFrame) -> pl.DataFrame:
    """Actual results per player and game, with official points as ppr_points."""
    return (
        _normalize_receiving_columns(stats)
        .with_columns(pl.col("fantasy_points_ppr").alias(POINTS_STAT))
        .select("season", "week", "player_id", *PREDICTED_STATS)
    )


def replay_week(seasons: list[int], season: int, week: int, stats: pl.DataFrame, schedule: pl.DataFrame) -> pl.DataFrame:
    """
    Train and predict one past week using only earlier games. Doesn't apply the live
    roster filter, because the roster data only reflects each player's latest status.
    """
    before = (season, week)
    weekly = build_training_dataset(seasons=seasons, min_games_for_player=0, before=before)
    weekly = weekly.filter(pl.col("season_type") == "REG")
    feature_columns = get_feature_columns(weekly)
    rushing_columns = get_rushing_feature_columns(weekly)
    models = train_stat_models(prepare_model_frame(weekly, feature_columns), feature_columns, rushing_columns)

    # Teams on bye have no row for this week, so their players drop out here.
    games = team_game_context(schedule.filter(pl.col("week") == week)).select("team", "opponent_team", *NEXT_GAME_CONTEXT)
    snapshot = build_latest_snapshot(seasons=seasons, before=before).drop("opponent_team", "season", "week", *NEXT_GAME_CONTEXT)
    snapshot = snapshot.join(games, on="team", how="inner")
    snapshot = prepare_inference_frame(snapshot, feature_columns + rushing_columns)
    snapshot = snapshot.with_columns(pl.lit(season).alias("season"), pl.lit(week).alias("week"))

    earlier = stats.filter((pl.col("season") < season) | ((pl.col("season") == season) & (pl.col("week") < week)))
    return build_log_rows(add_rank(predict_stats(models, snapshot), season_points(earlier, season)))


def print_scores(label: str, scores: list[dict], gate: dict) -> None:
    """Print one line per week, then the passing-bar result."""
    print(f"\n{label}")
    for s in scores:
        if "rank_correlation" not in s:
            print(f"  Week {s['week']}: {s['predicted']} predicted, not enough results yet")
            continue
        details = "  ".join(f"{stat} {s[f'{stat}_mae']:.2f}/{s[f'{stat}_baseline_mae']:.2f}" for stat in PREDICTED_STATS)
        print(f"  Week {s['week']}: {s['predicted']}/{TOP_N} predicted, {s['played']} played, rank {s['rank_correlation']:.2f}/{s['baseline_rank_correlation']:.2f}  MAE model/baseline: {details}")
    print(f"  Gate: {gate}")


def main() -> None:
    """Optionally replay past weeks, then score every prediction file that exists."""
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    season = nfl.get_current_season()
    seasons = list(range(FIRST_TRAIN_SEASON, season + 1))
    stats = data_loader.load_player_weekly_stats(seasons).filter(pl.col("position") == "WR")
    schedule = data_loader.load_schedules([season])
    regular = schedule.filter(pl.col("game_type") == "REG")

    # A week counts as finished once every one of its games has a result.
    completed_weeks = (
        regular.group_by("week").agg(pl.col("result").is_not_null().all().alias("done")).filter("done")["week"].sort().to_list()
    )

    live_path = os.path.join(PREDICTIONS_DIR, f"{season}.csv")
    replay_path = os.path.join(PREDICTIONS_DIR, f"{season}_replay.csv")

    if "--replay" in sys.argv:
        played_weeks = stats.filter((pl.col("season") == season) & (pl.col("season_type") == "REG"))["week"].unique().sort().to_list()
        # Week 1 has no games from this season to rank players by, so replays start at week 2.
        rows = [replay_week(seasons, season, week, stats, regular) for week in played_weeks if week >= 2]
        os.makedirs(PREDICTIONS_DIR, exist_ok=True)
        pl.concat(rows).sort("season", "week", "player_id").write_csv(replay_path)

    actuals = load_actuals(stats)
    report = {"season": season, "completed_weeks": completed_weeks}
    # Live starts empty, so the website can say tracking hasn't produced results yet.
    accuracy = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "season": season,
        "top_n": TOP_N,
        "live": {"weeks": [], "passed": False, "reason": "no finished weeks yet"},
    }
    # Each log as scored, kept for the player history below.
    logs: dict[str, pl.DataFrame] = {}
    for label, path in (("live", live_path), ("replay", replay_path)):
        if os.path.exists(path):
            log = pl.read_csv(path)
            if label == "live":
                log = live_weeks_only(log, season)
            logs[label] = log
            # A plain table of predicted vs actual, readable on GitHub.
            build_review(log, actuals).write_csv(path.removesuffix(".csv") + "_review.csv")
            scores = score_predictions(log, actuals)
            gate = check_gate(scores, completed_weeks)
            print_scores(f"{label} predictions ({path})", scores, gate)
            report[label] = {"scores": scores, "gate": gate}
            accuracy[label] = summarize_accuracy(scores, gate, completed_weeks)

    os.makedirs(PREDICTIONS_DIR, exist_ok=True)
    with open(os.path.join(PREDICTIONS_DIR, f"{season}_report.json"), "w", encoding="utf-8") as report_file:
        json.dump(report, report_file, indent=2)

    os.makedirs(os.path.dirname(ACCURACY_PATH), exist_ok=True)
    with open(ACCURACY_PATH, "w", encoding="utf-8") as accuracy_file:
        json.dump(accuracy, accuracy_file, indent=1)

    write_player_history(logs, actuals, completed_weeks, season)


def write_player_history(logs: dict[str, pl.DataFrame], actuals: pl.DataFrame, completed_weeks: list[int], season: int) -> None:
    """Write each currently projected player's weekly projected vs actual points for the site."""
    # ponytail: only players in projections.json, to keep the file small; widen to every logged player later.
    with open(PROJECTIONS_PATH, encoding="utf-8") as projections_file:
        player_ids = [p["player_id"] for p in json.load(projections_file)["players"]]
    # An empty frame stands in for a missing log, so either file can be absent.
    empty = pl.DataFrame(schema={"season": pl.Int64, "week": pl.Int64, "player_id": pl.String, f"pred_{POINTS_STAT}": pl.Float64})
    history = build_player_history(logs.get("live", empty), logs.get("replay", empty), actuals, completed_weeks, player_ids)
    output = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "season": season, "players": history}
    # Compact separators: one entry per player-week adds up, and nobody reads this by hand.
    with open(HISTORY_PATH, "w", encoding="utf-8") as history_file:
        json.dump(output, history_file, separators=(",", ":"))


if __name__ == "__main__":
    main()
