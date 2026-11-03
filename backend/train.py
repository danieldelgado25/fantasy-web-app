from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import nflreadpy as nfl
import polars as pl

from wr_predictor import data_loader
from wr_predictor.dataset_builder import (
    attach_next_game_context,
    build_latest_snapshot,
    build_training_dataset,
    filter_to_active_roster,
)
from wr_predictor.model import (
    get_feature_columns,
    get_rushing_feature_columns,
    predict_stats,
    prepare_inference_frame,
    prepare_model_frame,
    save_model,
    train_stat_models,
)
from wr_predictor.player_info import add_player_info
from wr_predictor.predictions import add_rank, build_log_rows, not_yet_kicked_off, season_points, upsert_log
from wr_predictor.stats import POINTS_STAT

"""
Trains one model per projected stat on all available regular-season data, then
writes this week's projections two ways: a JSON file the website reads, and a
season log used later to score predictions against actual results.
Also writes the model and snapshot the deprecated local Flask API reads.
Run from backend/: python train.py
"""

# Earliest season with usable stats. The latest is always the current season,
# so projections and training data roll forward without a yearly code change.
FIRST_TRAIN_SEASON = 2021

MODEL_PATH = "models/wr_ridge.joblib"
SNAPSHOT_PATH = "data/processed/wr_latest_snapshot.parquet"

# Served as a static file by the frontend.
PROJECTIONS_PATH = "../frontend/public/data/projections.json"

# Committed to the repo, so its git history shows each prediction predates kickoff.
PREDICTION_LOG_TEMPLATE = "predictions/{season}.csv"


def write_projections_file(rows: pl.DataFrame, path: str) -> None:
    """Write every projected player, best-ranked first, plus when it was generated."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "players": rows.sort("rank").to_dicts(),
    }
    with open(path, "w", encoding="utf-8") as projections_file:
        json.dump(payload, projections_file, indent=1)


def main() -> None:
    """Train the models, build the projectable players, and write every output."""
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    # Current season by NFL calendar: rolls over the Thursday after Labor Day.
    current_season = nfl.get_current_season()
    train_seasons = list(range(FIRST_TRAIN_SEASON, current_season + 1))
    # Includes next season so the upcoming game still resolves between seasons.
    schedule_lookup_seasons = [current_season, current_season + 1]

    # Regular season only: postseason games shouldn't count as a data point
    # to train on, though they still fed the rolling/lag trend leading into
    # them (see notebooks/02_ML_exploration.ipynb section 10 — dropping them
    # entirely changed 2025 backtest MAE by <0.01, so this is confirmed safe).
    weekly = build_training_dataset(seasons=train_seasons, min_games_for_player=0)
    weekly = weekly.filter(pl.col("season_type") == "REG")

    feature_columns = get_feature_columns(weekly)
    frame = prepare_model_frame(weekly, feature_columns)

    rushing_columns = get_rushing_feature_columns(weekly)
    models = train_stat_models(frame, feature_columns, rushing_columns)

    snapshot = build_latest_snapshot(seasons=train_seasons)
    # Roster year rolls over in March, ahead of the season year used above.
    snapshot = filter_to_active_roster(snapshot, season=nfl.get_current_season(roster=True))
    snapshot = attach_next_game_context(snapshot, seasons=schedule_lookup_seasons)
    snapshot = prepare_inference_frame(snapshot, feature_columns + rushing_columns)

    # Fail the build rather than publish nothing: on a failed build Render keeps
    # serving the last good deploy. Expected in the offseason, with no games ahead.
    if snapshot.is_empty():
        raise SystemExit("No projectable players (no upcoming games or roster data). Artifacts not written.")

    points_model, points_columns = models[POINTS_STAT]
    save_model(points_model, points_columns, MODEL_PATH)
    print(f"Trained {len(models)} models on {frame.height} rows. Saved the points model to {MODEL_PATH}")

    os.makedirs(os.path.dirname(SNAPSHOT_PATH) or ".", exist_ok=True)
    snapshot.write_parquet(SNAPSHOT_PATH)

    stats = data_loader.load_player_weekly_stats(train_seasons).filter(pl.col("position") == "WR")
    ranked = add_rank(predict_stats(models, snapshot), season_points(stats, current_season))
    # Display details go only to the website file; the prediction log keeps its columns.
    site_rows = add_player_info(
        build_log_rows(ranked), data_loader.load_players(), data_loader.load_teams(), stats, current_season
    )
    write_projections_file(site_rows, PROJECTIONS_PATH)
    print(f"Wrote {ranked.height} player projections to {PROJECTIONS_PATH}")

    # Games that have started are left out, so their logged predictions stay frozen.
    upcoming = not_yet_kicked_off(ranked, datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None))
    log_path = PREDICTION_LOG_TEMPLATE.format(season=current_season)
    if not upcoming.is_empty():
        upsert_log(log_path, build_log_rows(upcoming))
    print(f"Logged {upcoming.height} predictions for games not yet started to {log_path}")


if __name__ == "__main__":
    main()
