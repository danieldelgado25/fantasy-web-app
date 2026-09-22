from __future__ import annotations

import os
import sys

import polars as pl
from sklearn.linear_model import Ridge

from wr_predictor.dataset_builder import attach_next_game_context, build_latest_snapshot, build_training_dataset
from wr_predictor.model import get_feature_columns, prepare_model_frame, save_model

"""
Trains the production next-week-PPR model on all available regular-season
data and writes it, plus a live per-player snapshot, to disk — the two
artifacts backend/api/routes.py needs to stop returning its 501 stub.
Run from backend/: python train.py
"""

# All seasons with usable stats, used for both training and the snapshot's
# own trailing/rolling features.
TRAIN_SEASONS = [2021, 2022, 2023, 2024, 2025]

# The season being projected into. Used both to bound the schedule lookup
# and to drop players whose "next game" only resolved to a stale season
# (e.g. a retired player last seen in 2023 — their team's next game after
# that isn't a real projection candidate).
CURRENT_SEASON = 2026
SCHEDULE_LOOKUP_SEASONS = [CURRENT_SEASON - 1, CURRENT_SEASON]

MODEL_PATH = "models/wr_ridge.joblib"
SNAPSHOT_PATH = "data/processed/wr_latest_snapshot.parquet"


def main() -> None:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")

    # Regular season only: postseason games shouldn't count as a data point
    # to train on, though they still fed the rolling/lag trend leading into
    # them (see notebooks/02_ML_exploration.ipynb section 10 — dropping them
    # entirely changed 2025 backtest MAE by <0.01, so this is confirmed safe).
    weekly = build_training_dataset(seasons=TRAIN_SEASONS, min_games_for_player=0)
    weekly = weekly.filter(pl.col("season_type") == "REG")

    feature_columns = get_feature_columns(weekly)
    frame = prepare_model_frame(weekly, feature_columns)

    model = Ridge(alpha=1.0)
    model.fit(frame.select(feature_columns).to_numpy(), frame["next_week_ppr_points"].to_numpy())
    save_model(model, feature_columns, MODEL_PATH)
    print(f"Trained on {frame.height} rows, {len(feature_columns)} features. Saved model to {MODEL_PATH}")

    snapshot = build_latest_snapshot(seasons=TRAIN_SEASONS)
    snapshot = attach_next_game_context(snapshot, seasons=SCHEDULE_LOOKUP_SEASONS)
    snapshot = snapshot.filter(pl.col("season") == CURRENT_SEASON)
    os.makedirs(os.path.dirname(SNAPSHOT_PATH) or ".", exist_ok=True)
    snapshot.write_parquet(SNAPSHOT_PATH)
    print(f"Wrote {snapshot.height} player snapshots (next-game context attached) to {SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
