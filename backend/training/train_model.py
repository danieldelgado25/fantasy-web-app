"""
train_model.py
===============

WHY THIS FILE EXISTS
---------------------
The Flask API is a *serving* layer, not a *training* layer. It should never
train on request -- that would be slow, non-reproducible, and would tie every
API response to the last run's random state. Instead we train once, offline,
and serialize the fitted model to a `.joblib` artifact that `model_service.py`
loads at request time. Standard ML separation: an offline training pipeline and
an online inference pipeline, joined by a versioned artifact.

WHAT THIS SCRIPT IS
-------------------
A thin CLI over two things this repo already owns:
  - `wr_predictor.dataset_builder.build_training_dataset` -- feature engineering
  - `wr_predictor.model` -- the canonical modeling API (split, pipeline factory,
    alpha selection, metrics)

It does NOT define any modeling logic of its own. Everything about *how* the
model is built lives in `src/wr_predictor/model.py`, so the artifact shipped
here and the numbers `main.py` prints come from the same code path. This script
only: builds the dataset, calls those helpers over a chosen season split,
reports baseline-vs-Ridge metrics, and writes the artifact + a metrics.json.

USAGE
-----
    python training/train_model.py

Requires `pip install -e ".[webapp]"` from the repo root -- that is what makes
`import wr_predictor` resolve.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib

from wr_predictor.dataset_builder import build_training_dataset
from wr_predictor.model import (
    BASELINE_COLUMN,
    DEFAULT_ALPHA_GRID,
    TARGET_COLUMN,
    feature_matrix,
    get_feature_columns,
    prepare_model_frame,
    regression_metrics,
    select_best_ridge,
    split_train_val_test,
)

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
# Time-based split. Train on the older seasons, validate on the next, hold out
# the two most recent for test -- the real deployment scenario (predicting
# seasons the model has never seen). 2016 floor: reliable air-yards / target-
# share tracking starts then. Roll these forward as new seasons land so the
# test set stays a genuine future holdout.
TRAIN_SEASONS = list(range(2016, 2023))  # 2016-2022
VAL_SEASONS = [2023]
TEST_SEASONS = [2024, 2025]
ALL_SEASONS = sorted(set(TRAIN_SEASONS) | set(VAL_SEASONS) | set(TEST_SEASONS))

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"
ARTIFACT_PATH = ARTIFACT_DIR / "wr_model_v1.joblib"
METRICS_PATH = ARTIFACT_DIR / "wr_model_v1.metrics.json"


def _score_splits(splits: dict, predict) -> dict:
    """Run `predict(frame)` on each named split and score it against the
    target. `predict` takes a polars frame and returns predictions."""
    return {
        name: regression_metrics(frame[TARGET_COLUMN].to_numpy(), predict(frame))
        for name, frame in splits.items()
    }


def main() -> None:
    print(f"Building WR weekly dataset for seasons {ALL_SEASONS[0]}-{ALL_SEASONS[-1]}...")
    t0 = time.time()

    # merge_ff_opportunity left at its default (False). The opponent-adjusted
    # expected-fantasy-points columns it adds are optional; enable them here
    # (and retrain) once the serving path is ready to build features the same
    # way. The serving path must match whatever is chosen here.
    weekly = build_training_dataset(seasons=ALL_SEASONS, min_games_for_player=0)
    print(f"  -> {weekly.shape[0]} rows, {weekly.shape[1]} cols in {time.time() - t0:.1f}s")

    feature_cols = get_feature_columns(weekly)
    # Default require="rolling_3": drop only rows missing 3-week history or the
    # label. temp/wind nulls (every dome game) are kept and median-imputed
    # inside the pipeline rather than deleting the player-week.
    model_frame = prepare_model_frame(weekly, feature_cols)

    train, val, test = split_train_val_test(
        model_frame, TRAIN_SEASONS, VAL_SEASONS, TEST_SEASONS
    )
    splits = {"train": train, "val": val, "test": test}
    print(f"Split sizes -> train={train.height} val={val.height} test={test.height}")

    # Baseline: predict next week as the trailing 3-week average. No fitting --
    # the bar the trained model must clear to justify existing.
    baseline_metrics = _score_splits(
        splits, lambda frame: frame[BASELINE_COLUMN].to_numpy()
    )
    print("Baseline (rolling-3-week avg) test:", baseline_metrics["test"])

    # Ridge, alpha chosen on validation RMSE.
    best = select_best_ridge(train, val, feature_cols, DEFAULT_ALPHA_GRID)
    ridge_metrics = _score_splits(
        splits, lambda frame: best["model"].predict(feature_matrix(frame, feature_cols))
    )
    print(f"Ridge (alpha={best['alpha']}) test:", ridge_metrics["test"])

    beats_baseline = ridge_metrics["test"]["rmse"] < baseline_metrics["test"]["rmse"]
    print(f"Ridge beats rolling-average baseline on test RMSE? {beats_baseline}")

    # Serialize model + everything model_service needs to use it correctly.
    # feature_cols order matters: sklearn predicts by column position.
    artifact = {
        "model": best["model"],
        "feature_cols": feature_cols,
        "target_col": TARGET_COLUMN,
        "baseline_col": BASELINE_COLUMN,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "train_seasons": TRAIN_SEASONS,
        "val_seasons": VAL_SEASONS,
        "test_seasons": TEST_SEASONS,
        "best_alpha": best["alpha"],
        "metrics": {
            "ridge": ridge_metrics,
            "baseline_rolling_avg": baseline_metrics,
            "beats_baseline_on_test_rmse": beats_baseline,
        },
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, ARTIFACT_PATH)
    print(f"Saved artifact to {ARTIFACT_PATH}")

    # Human-readable sidecar so metrics can be diffed between runs without
    # unpickling anything.
    with open(METRICS_PATH, "w") as f:
        json.dump({k: v for k, v in artifact.items() if k != "model"}, f, indent=2, default=str)
    print(f"Saved metrics summary to {METRICS_PATH}")


if __name__ == "__main__":
    main()
