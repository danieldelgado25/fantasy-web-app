from __future__ import annotations

from collections.abc import Sequence

import polars as pl
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

"""
The canonical modeling layer for next_week_ppr_points: feature selection, row
preparation, the season-based split, the Ridge pipeline, alpha selection, and
metrics.

There is ONE implementation of "how the model is built" and it is here.
`backend/training/train_model.py` and `main.py` are both thin callers of these
functions, so the artifact the trainer ships and the numbers main.py prints
come from the same code.

Season-based split, never random: training on a player's future games and
validating on their past leaks information and makes the metrics a lie. Train
on older seasons, validate on the next, test on the most recent held-out
seasons -- the real deployment scenario.
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

# Supervised target: the player's PPR points in their *following* game.
TARGET_COLUMN = "next_week_ppr_points"

# Naive predictor the trained model must beat: the player's trailing 3-week PPR
# average, a column the dataset builder already computes (zero fitting).
BASELINE_COLUMN = "ppr_points_rolling_3"

# Ridge regularization strengths tried by `select_best_ridge`, chosen on
# validation RMSE. Small and log-spaced: with this few features Ridge is
# already low-variance, so the grid only needs to bracket "barely" to
# "heavily" regularized.
DEFAULT_ALPHA_GRID: tuple[float, ...] = (0.1, 1.0, 10.0)


def get_feature_columns(data_frame: pl.DataFrame) -> list[str]:
    """
    Return the model-input columns: every numeric column that is not a
    meta/identifier column and not the target.

    Non-numeric columns are excluded because the pipeline's imputer and scaler
    only operate on numbers.
    """
    exclude = set(META_COLUMNS) | {TARGET_COLUMN}
    return [
        column
        for column, dtype in data_frame.schema.items()
        if column not in exclude and dtype.is_numeric()
    ]


def prepare_model_frame(
    data_frame: pl.DataFrame,
    feature_columns: list[str],
    *,
    require: str = "rolling_3",
) -> pl.DataFrame:
    """
    Drop rows that can't be used for supervised training, and report the loss.

    `require` controls how aggressive the null-drop is:
      - "rolling_3" (default): require only the `*_rolling_3` feature columns
        and the target to be non-null. A player's first two tracked games have
        no 3-week history yet (structurally unusable), but dome games -- null
        `temp`/`wind` by construction -- are kept and median-imputed inside the
        model pipeline rather than deleted.
      - "all": require every feature column and the target to be non-null. The
        strict legacy behavior; disproportionately drops dome-team players.
    """
    if require == "all":
        required = list(feature_columns) + [TARGET_COLUMN]
    elif require == "rolling_3":
        required = [c for c in feature_columns if c.endswith("_rolling_3")] + [TARGET_COLUMN]
    else:
        raise ValueError(f"require must be 'rolling_3' or 'all', got {require!r}")

    before = data_frame.height
    cleaned = data_frame.drop_nulls(subset=required)
    dropped = before - cleaned.height
    if dropped:
        print(f"Dropped {dropped} of {before} rows missing required values (require={require!r}).")
    return cleaned


def evaluate_baseline(frame: pl.DataFrame) -> dict[str, float]:
    """
    Score the naive baseline on `frame`: predict `next_week_ppr_points` as the
    player's trailing 3-week average (`BASELINE_COLUMN`). No fitting -- this is
    the bar the trained model must clear to justify existing. Returns the same
    mae/rmse/r2/n shape as `regression_metrics`.
    """
    return regression_metrics(
        frame[TARGET_COLUMN].to_numpy(),
        frame[BASELINE_COLUMN].to_numpy(),
    )


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
