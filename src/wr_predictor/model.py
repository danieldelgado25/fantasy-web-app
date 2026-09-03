from __future__ import annotations

from collections.abc import Sequence

import polars as pl
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

"""
Baseline and first-pass model training/evaluation for next_week_ppr_points.
Uses a season-based train/validation split (train on past seasons, validate
on a held-out future season) so no future-game information leaks into
training, and so results reflect the real deployment scenario: predicting
a season the model has never seen.
"""

# Columns that identify a row but are not model inputs.
META_COLUMNS = [
    "player_id",
    "player_name",
    "player_display_name",
    "season",
    "week",
    "season_type",
    "team",
    "opponent_team",
    "home_away",
]

TARGET_COLUMN = "next_week_ppr_points"


def split_by_season(
    data_frame: pl.DataFrame,
    train_seasons: list[int],
    validation_seasons: list[int],
) -> tuple[pl.DataFrame, pl.DataFrame]:
    """
    Split into train/validation by season, keeping validation seasons
    strictly separate from training seasons (no shared player-weeks).
    """
    train = data_frame.filter(pl.col("season").is_in(train_seasons))
    validation = data_frame.filter(pl.col("season").is_in(validation_seasons))
    return train, validation


def get_feature_columns(data_frame: pl.DataFrame) -> list[str]:
    """
    Every column except identifier/meta columns and the target is a
    candidate model feature.
    """
    exclude = set(META_COLUMNS) | {TARGET_COLUMN}
    return [col for col in data_frame.columns if col not in exclude]


def prepare_model_frame(data_frame: pl.DataFrame, feature_columns: list[str]) -> pl.DataFrame:
    """
    Drop rows with a null in any feature or the target. Nulls occur mainly
    for a player's first tracked game, which has no prior week to build
    lag/rolling features from. Reports how many rows were dropped so the
    loss is visible rather than silent.
    """
    required = feature_columns + [TARGET_COLUMN]
    before = data_frame.height
    cleaned = data_frame.drop_nulls(subset=required)
    dropped = before - cleaned.height
    if dropped:
        print(f"Dropped {dropped} of {before} rows with missing feature/target values.")
    return cleaned


def evaluate_baseline(validation: pl.DataFrame) -> dict[str, float]:
    """
    Naive baseline: predict next week's points as this week's trailing
    3-game rolling average. Any real model must beat this to be worth using.
    """
    actual = validation[TARGET_COLUMN].to_numpy()
    predicted = validation["ppr_points_rolling_3"].to_numpy()
    return {
        "mae": mean_absolute_error(actual, predicted),
        "rmse": mean_squared_error(actual, predicted) ** 0.5,
    }


def train_and_evaluate_ridge(
    train: pl.DataFrame,
    validation: pl.DataFrame,
    feature_columns: list[str],
) -> dict[str, float]:
    """
    Fit a Ridge regression (linear model with L2 regularization) on the
    training seasons and evaluate on the held-out validation season.
    Chosen as the first model because it is low-variance and hard to
    overfit with this few features, giving a fair bar for later models
    (e.g. gradient boosting) to clear.
    """
    x_train = train.select(feature_columns).to_numpy()
    y_train = train[TARGET_COLUMN].to_numpy()
    x_validation = validation.select(feature_columns).to_numpy()
    y_validation = validation[TARGET_COLUMN].to_numpy()

    model = Ridge(alpha=1.0)
    model.fit(x_train, y_train)
    predictions = model.predict(x_validation)

    return {
        "mae": mean_absolute_error(y_validation, predictions),
        "rmse": mean_squared_error(y_validation, predictions) ** 0.5,
    }


# ---------------------------------------------------------------------------
# Canonical modeling API
# ---------------------------------------------------------------------------
# The functions below are the single source of truth for "how the model is
# built and scored". backend/training/train_model.py is a thin CLI over them
# (build dataset -> prepare -> split -> select alpha -> serialize), so the
# artifact it ships and the numbers main.py prints come from the same code.

# Naive predictor the trained model must beat: the player's trailing 3-week PPR
# average, a column the dataset builder already computes (zero fitting).
BASELINE_COLUMN = "ppr_points_rolling_3"

# Ridge regularization strengths tried by `select_best_ridge`, chosen on
# validation RMSE. Small and log-spaced: with this few features Ridge is
# already low-variance, so the grid only needs to bracket "barely" to
# "heavily" regularized.
DEFAULT_ALPHA_GRID: tuple[float, ...] = (0.1, 1.0, 10.0)


def split_train_val_test(
    data_frame: pl.DataFrame,
    train_seasons: Sequence[int],
    validation_seasons: Sequence[int],
    test_seasons: Sequence[int],
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """
    Partition rows into train / validation / test by season.

    The three season groups must not overlap; each returned frame contains only
    rows whose `season` is in the matching group. Rows from a season in none of
    the groups are dropped. Splitting by season (not randomly) is what keeps a
    player's future games out of the data used to predict their past.
    """
    groups = [set(train_seasons), set(validation_seasons), set(test_seasons)]
    for a, b in ((0, 1), (0, 2), (1, 2)):
        overlap = groups[a] & groups[b]
        if overlap:
            raise ValueError(f"season groups overlap on {sorted(overlap)}")

    return (
        data_frame.filter(pl.col("season").is_in(list(train_seasons))),
        data_frame.filter(pl.col("season").is_in(list(validation_seasons))),
        data_frame.filter(pl.col("season").is_in(list(test_seasons))),
    )


def build_model_pipeline(alpha: float = 1.0) -> Pipeline:
    """
    The model as one fitted-together object: median-impute remaining nulls
    (mostly `temp`/`wind` on dome games, which have no weather reading),
    standardize so Ridge's single alpha penalizes every coefficient on a
    comparable scale, then Ridge itself. `random_state` is fixed for
    reproducible runs.
    """
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            ("ridge", Ridge(alpha=alpha, random_state=0)),
        ]
    )


def feature_matrix(frame: pl.DataFrame, feature_columns: list[str]):
    """Return `frame`'s feature columns, in order, as a NumPy array for
    sklearn `.fit` / `.predict`."""
    return frame.select(feature_columns).to_numpy()


def _rmse(y_true, y_pred) -> float:
    """RMSE computed manually so this works across sklearn versions whether or
    not `root_mean_squared_error` exists."""
    return float(mean_squared_error(y_true, y_pred) ** 0.5)


def regression_metrics(y_true, y_pred) -> dict[str, float]:
    """
    One definition of "how good is this prediction", so every split
    (train/val/test) and every predictor (baseline/Ridge) is scored the same
    way and the numbers are comparable. Returns mae, rmse, r2, and n.
    """
    return {
        "mae": round(mean_absolute_error(y_true, y_pred), 4),
        "rmse": round(_rmse(y_true, y_pred), 4),
        "r2": round(r2_score(y_true, y_pred), 4),
        "n": int(len(y_true)),
    }


def select_best_ridge(
    train: pl.DataFrame,
    validation: pl.DataFrame,
    feature_columns: list[str],
    alpha_grid: Sequence[float] = DEFAULT_ALPHA_GRID,
) -> dict:
    """
    Fit `build_model_pipeline(alpha)` on the training rows for each alpha in
    `alpha_grid` and keep the one with the lowest validation RMSE.

    Returns `{"alpha": float, "model": Pipeline, "val_rmse": float}` -- ready
    for the caller to evaluate on the held-out test set and serialize.
    """
    if not list(alpha_grid):
        raise ValueError("alpha_grid must contain at least one alpha")

    x_train = feature_matrix(train, feature_columns)
    y_train = train[TARGET_COLUMN].to_numpy()
    x_val = feature_matrix(validation, feature_columns)
    y_val = validation[TARGET_COLUMN].to_numpy()

    best: dict = {}
    for alpha in alpha_grid:
        pipeline = build_model_pipeline(alpha=alpha)
        pipeline.fit(x_train, y_train)
        val_rmse = _rmse(y_val, pipeline.predict(x_val))
        if not best or val_rmse < best["val_rmse"]:
            best = {"alpha": float(alpha), "model": pipeline, "val_rmse": val_rmse}
    return best
