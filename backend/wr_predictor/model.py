from __future__ import annotations

import polars as pl
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error

from wr_predictor.stats import next_week_column, PREDICTED_STATS, RUSHING_STATS

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
    Model inputs: every column except identifiers, targets and rushing features,
    which are added separately for rushing projections only.
    """
    return [
        col
        for col in data_frame.columns
        if col not in META_COLUMNS and not col.startswith("next_week_") and not _is_rushing_feature(col)
    ]


def get_rushing_feature_columns(data_frame: pl.DataFrame) -> list[str]:
    """Rushing lag and rolling-average columns, used as inputs for rushing projections."""
    return [col for col in data_frame.columns if _is_rushing_feature(col)]


def _is_rushing_feature(column: str) -> bool:
    """True for a column derived from a rushing stat, such as carries_rolling_3."""
    return any(column.startswith(f"{stat}_") for stat in RUSHING_STATS)


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


def prepare_inference_frame(snapshot: pl.DataFrame, feature_columns: list[str]) -> pl.DataFrame:
    """
    Drop snapshot rows the model can't score: a null feature would make it raise
    at request time. Happens for a player with no earlier game to build lag
    features from. Reports the count so it stays visible.
    """
    cleaned = snapshot.drop_nulls(subset=feature_columns)
    dropped = snapshot.height - cleaned.height
    if dropped:
        print(f"Dropped {dropped} of {snapshot.height} snapshot rows with missing feature values.")
    return cleaned


def train_stat_models(
    frame: pl.DataFrame,
    feature_columns: list[str],
    rushing_feature_columns: list[str],
) -> dict[str, tuple[Ridge, list[str]]]:
    """
    Fit one Ridge regression per predicted stat, so each can be scored against its
    own actual result. Returns {stat: (model, the input columns it was fit on)}.
    """
    models = {}
    for stat in PREDICTED_STATS:
        target = next_week_column(stat)
        if target not in frame.columns:
            continue
        columns = feature_columns + rushing_feature_columns if stat in RUSHING_STATS else feature_columns
        rows = frame.drop_nulls(subset=[*columns, target])
        model = Ridge(alpha=1.0)
        model.fit(rows.select(columns).to_numpy(), rows[target].to_numpy())
        models[stat] = (model, columns)
    return models


def predict_stats(models: dict[str, tuple[Ridge, list[str]]], frame: pl.DataFrame) -> pl.DataFrame:
    """
    Add a pred_<stat> column per model, floored at 0 because a linear model can go
    slightly negative for low-usage players and none of these stats should.
    """
    return frame.with_columns(
        [
            pl.Series(f"pred_{stat}", model.predict(frame.select(columns).to_numpy())).clip(lower_bound=0.0)
            for stat, (model, columns) in models.items()
        ]
    )


def evaluate_baseline(validation: pl.DataFrame) -> dict[str, float]:
    """
    Naive baseline: predict next week's points as the average of the player's
    last 3 games, including the latest. Any real model must beat this to be worth using.
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
