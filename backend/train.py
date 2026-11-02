from __future__ import annotations

import os
import sys

import nflreadpy as nfl
import polars as pl
from sklearn.linear_model import Ridge

from wr_predictor.dataset_builder import (
    attach_next_game_context,
    build_latest_snapshot,
    build_training_dataset,
    filter_to_active_roster,
)
from wr_predictor.model import get_feature_columns, prepare_inference_frame, prepare_model_frame, save_model

"""
Trains the production next-week-PPR model on all available regular-season
data and writes it, plus a live per-player snapshot, to disk — the two
artifacts backend/api/routes.py needs to stop returning its 501 stub.
Run from backend/: python train.py
"""

# Earliest season with usable stats. The latest is always the current season,
# so projections and training data roll forward without a yearly code change.
FIRST_TRAIN_SEASON = 2021

MODEL_PATH = "models/wr_ridge.joblib"
SNAPSHOT_PATH = "data/processed/wr_latest_snapshot.parquet"


def main() -> None:
    """Train the model, then build and write the snapshot of projectable players."""
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

    model = Ridge(alpha=1.0)
    model.fit(frame.select(feature_columns).to_numpy(), frame["next_week_ppr_points"].to_numpy())

    snapshot = build_latest_snapshot(seasons=train_seasons)
    # Roster year rolls over in March, ahead of the season year used above.
    snapshot = filter_to_active_roster(snapshot, season=nfl.get_current_season(roster=True))
    snapshot = attach_next_game_context(snapshot, seasons=schedule_lookup_seasons)
    snapshot = prepare_inference_frame(snapshot, feature_columns)

    # Fail the build rather than publish nothing: on a failed build Render keeps
    # serving the last good deploy. Expected in the offseason, with no games ahead.
    if snapshot.is_empty():
        raise SystemExit("No projectable players (no upcoming games or roster data). Artifacts not written.")

    save_model(model, feature_columns, MODEL_PATH)
    print(f"Trained on {frame.height} rows, {len(feature_columns)} features. Saved model to {MODEL_PATH}")

    os.makedirs(os.path.dirname(SNAPSHOT_PATH) or ".", exist_ok=True)
    snapshot.write_parquet(SNAPSHOT_PATH)
    print(f"Wrote {snapshot.height} player snapshots (next-game context attached) to {SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
