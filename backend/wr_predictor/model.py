from __future__ import annotations

import polars as pl
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error

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
