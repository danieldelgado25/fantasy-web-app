"""
train_model.py
===============

WHY THIS FILE EXISTS
---------------------
The web app's Flask API is a *serving* layer, not a *training* layer. It should
never train a model on request — that would be slow, non-reproducible, and would
tie every API response to whatever random state the last training run happened to
land on. Instead, we train once, offline, and save ("serialize") the fitted model
to disk as an artifact. The API then just loads that artifact and calls
`.predict()` on it. This is the standard separation in ML systems: an offline
*training pipeline* and an online *inference/serving* pipeline, joined by a
versioned artifact file.

This script is deliberately a thin wrapper around this repo's `wr_predictor`
pipeline package (`dataset_builder`, `features`, `targets`). We are NOT
reimplementing feature engineering here — we import and reuse it, exactly as
`notebooks/02_ML_exploration.ipynb` does. The web app (backend/) and the ML
pipeline (src/wr_predictor/) live in the same repo but stay cleanly separated:
the pipeline knows nothing about Flask; this script only consumes its output.

WHAT THIS SCRIPT DOES
----------------------
1. Imports `build_training_dataset` from the `wr_predictor` package.
2. Builds a WR weekly dataset the same way the notebook does (schedule context,
   lag features, rolling averages, `next_week_ppr_points` target).
3. Splits by *season*, not randomly — this matters a lot for time-series sports
   data. If we split randomly, the model could "see" a player's future games
   during training (e.g. train on Week 10 but validate on Week 3 of the same
   season), which leaks information and makes validation numbers a lie.
4. Trains a Ridge regression (matching the notebook's chosen model family) with
   a small alpha grid, selected on validation RMSE.
5. Computes a "dumb baseline" — just predicting next week's points as the
   player's trailing 3-week rolling average, with ZERO model fitting involved.
   This is the most important step for honestly evaluating the model: if Ridge
   doesn't beat this baseline, the model isn't adding value over "look at their
   recent form," and that's worth knowing before shipping it behind an API.
6. Serializes model + baseline metrics + feature column list + metadata to a
   single `.joblib` artifact that `model_service.py` loads at request time.

USAGE
-----
    python training/train_model.py

Requires the pipeline package to be installed (`pip install -e .` from the
repo root, or `pip install -e .[webapp]`). That is what makes
`import wr_predictor` resolve here.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

# --------------------------------------------------------------------------
# Import the wide-receiver-predictor pipeline
# --------------------------------------------------------------------------
# The pipeline is this repo's own `wr_predictor` package (see pyproject.toml),
# not a copy of dataset_builder/features/targets living in the web app. Import
# it directly; `pip install -e .` is what puts it on the path. No sys.path
# juggling and no separate checkout to locate.
from wr_predictor.dataset_builder import build_training_dataset

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
# Time-based split, matching notebooks/02_ML_exploration.ipynb so the artifact
# this script produces is directly comparable to the notebook's numbers.
TRAIN_SEASONS = list(range(2016, 2022))   # 2016-2021
VAL_SEASONS = [2022]
TEST_SEASONS = [2023, 2024]
ALL_SEASONS = sorted(set(TRAIN_SEASONS) | set(VAL_SEASONS) | set(TEST_SEASONS))

ALPHA_GRID = [0.1, 1.0, 10.0]

ARTIFACT_DIR = Path(__file__).resolve().parents[1] / "artifacts"
ARTIFACT_PATH = ARTIFACT_DIR / "wr_model_v1.joblib"

TARGET_COL = "next_week_ppr_points"
BASELINE_COL = "ppr_points_rolling_3"  # trailing 3-week average — the "dumb" predictor


def root_mean_squared_error(y_true, y_pred) -> float:
    """sklearn only added a direct RMSE helper in newer versions; compute it
    manually so this script works across sklearn versions without guessing
    which API is available."""
    return float(mean_squared_error(y_true, y_pred) ** 0.5)


def regression_metrics(y_true, y_pred) -> dict:
    """One place that defines what 'how good is this model' means, so every
    split (train/val/test) and every model (baseline/ridge) is scored
    identically and the numbers are actually comparable."""
    return {
        "mae": round(mean_absolute_error(y_true, y_pred), 4),
        "rmse": round(root_mean_squared_error(y_true, y_pred), 4),
        "r2": round(r2_score(y_true, y_pred), 4),
        "n": int(len(y_true)),
    }


def main() -> None:
    print(f"Building WR weekly dataset for seasons {ALL_SEASONS[0]}-{ALL_SEASONS[-1]}...")
    t0 = time.time()

    # merge_ff_opportunity=False: as of this training run, that join in
    # dataset_builder._merge_ff_opportunity raises a polars SchemaError
    # (season dtype mismatch: int on the weekly frame vs string on the
    # ff_opportunity frame) and crashes dataset construction entirely.
    # That's a bug in wide-receiver-predictor, not something to silently
    # work around in the web app — flagged in the handoff notes/README
    # rather than patched here, since this repo shouldn't be the place
    # pipeline bugs get fixed.
    weekly = build_training_dataset(
        seasons=ALL_SEASONS,
        min_games_for_player=0,
        merge_ff_opportunity=False,
    )
    print(f"  -> {weekly.shape[0]} rows, {weekly.shape[1]} cols in {time.time() - t0:.1f}s")

    df = weekly.to_pandas()

    id_cols = [
        c
        for c in (
            "player_id",
            "player_name",
            "player_display_name",
            "season",
            "week",
            "season_type",
            "team",
            "opponent_team",
        )
        if c in df.columns
    ]
    feature_cols = [
        c
        for c in df.columns
        if c not in id_cols
        and c != TARGET_COL
        and pd.api.types.is_numeric_dtype(df[c])
    ]

    # Require the rolling-3 columns to be non-null (a rookie's first couple of
    # games won't have 3 prior weeks yet — that's structural, so we drop those
    # rows) and require the target to be non-null (nothing to learn from a row
    # with no label). We deliberately DON'T blanket-dropna every feature
    # column the way the notebook does: `temp`/`wind` are null for every dome
    # game by construction (there's no wind chill inside a stadium), and a
    # naive dropna there silently discards ~40% of rows — disproportionately
    # removing dome-team players from training entirely, which biases the
    # model against players who happen to play indoors. Instead, those
    # environmental columns are median-imputed inside the model pipeline
    # below (see the "impute" step), so a genuinely missing reading gets a
    # neutral fill-in rather than deleting the whole player-week.
    roll3_cols = [c for c in df.columns if c.endswith("_rolling_3")]
    if roll3_cols:
        df = df.dropna(subset=roll3_cols)
    df = df.dropna(subset=[TARGET_COL])

    train_mask = df["season"].isin(TRAIN_SEASONS)
    val_mask = df["season"].isin(VAL_SEASONS)
    test_mask = df["season"].isin(TEST_SEASONS)

    X_train, y_train = df.loc[train_mask, feature_cols], df.loc[train_mask, TARGET_COL]
    X_val, y_val = df.loc[val_mask, feature_cols], df.loc[val_mask, TARGET_COL]
    X_test, y_test = df.loc[test_mask, feature_cols], df.loc[test_mask, TARGET_COL]
    print(f"Split sizes -> train={len(X_train)} val={len(X_val)} test={len(X_test)}")

    # ----------------------------------------------------------------
    # Baseline: "predict the rolling 3-week average, nothing fancier"
    # ----------------------------------------------------------------
    # This has NO fitted parameters at all — it's just reading a column that
    # dataset_builder already computed. It is the bar the real model has to
    # clear to justify existing.
    baseline_metrics = {
        "train": regression_metrics(y_train, df.loc[train_mask, BASELINE_COL]),
        "val": regression_metrics(y_val, df.loc[val_mask, BASELINE_COL]),
        "test": regression_metrics(y_test, df.loc[test_mask, BASELINE_COL]),
    }
    print("Baseline (rolling-3-week avg) test metrics:", baseline_metrics["test"])

    # ----------------------------------------------------------------
    # Ridge regression, alpha selected on validation RMSE
    # ----------------------------------------------------------------
    best_alpha, best_val_rmse, best_model = None, None, None
    for alpha in ALPHA_GRID:
        pipe = Pipeline([
            # median-fill any remaining nulls (temp/wind on dome/missing-data
            # games being the main source — see the dropna comment above)
            # BEFORE scaling, so StandardScaler never sees a NaN either.
            ("impute", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("ridge", Ridge(alpha=alpha, random_state=0)),
        ])
        pipe.fit(X_train, y_train)
        val_rmse = root_mean_squared_error(y_val, pipe.predict(X_val))
        if best_val_rmse is None or val_rmse < best_val_rmse:
            best_alpha, best_val_rmse, best_model = alpha, val_rmse, pipe

    ridge_metrics = {
        "train": regression_metrics(y_train, best_model.predict(X_train)),
        "val": regression_metrics(y_val, best_model.predict(X_val)),
        "test": regression_metrics(y_test, best_model.predict(X_test)),
    }
    print(f"Ridge (alpha={best_alpha}) test metrics:", ridge_metrics["test"])

    beats_baseline = ridge_metrics["test"]["rmse"] < baseline_metrics["test"]["rmse"]
    print(f"Ridge beats rolling-average baseline on test RMSE? {beats_baseline}")

    # ----------------------------------------------------------------
    # Serialize: model + everything the serving layer needs to use it
    # correctly, without having to re-derive it from the notebook by hand.
    # ----------------------------------------------------------------
    artifact = {
        "model": best_model,
        "feature_cols": feature_cols,
        "target_col": TARGET_COL,
        "baseline_col": BASELINE_COL,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "train_seasons": TRAIN_SEASONS,
        "val_seasons": VAL_SEASONS,
        "test_seasons": TEST_SEASONS,
        "best_alpha": best_alpha,
        "metrics": {
            "ridge": ridge_metrics,
            "baseline_rolling_avg": baseline_metrics,
            "beats_baseline_on_test_rmse": beats_baseline,
        },
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, ARTIFACT_PATH)
    print(f"Saved artifact to {ARTIFACT_PATH}")

    # Also drop a small human-readable metrics.json next to it, so metrics can
    # be checked (or diffed between training runs) without unpickling anything.
    metrics_path = ARTIFACT_DIR / "wr_model_v1.metrics.json"
    with open(metrics_path, "w") as f:
        json.dump({k: v for k, v in artifact.items() if k != "model"}, f, indent=2, default=str)
    print(f"Saved metrics summary to {metrics_path}")


if __name__ == "__main__":
    main()
