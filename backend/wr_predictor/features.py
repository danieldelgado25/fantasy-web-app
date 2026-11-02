from __future__ import annotations

import polars as pl

from wr_predictor.stats import FEATURE_STATS, next_week_column, PREDICTED_STATS


def add_basic_fantasy_points(data_frame: pl.DataFrame) -> pl.DataFrame:
    """
    Add a ppr_points column. Prefers nflverse's official fantasy_points_ppr, which
    also counts rushing, 2-point conversions and fumbles, and works for any position.
    Falls back to receiving only (1 per reception, 0.1 per yard, 6 per touchdown)
    for data without the official column.
    """
    if "fantasy_points_ppr" in data_frame.columns:
        return data_frame.with_columns(pl.col("fantasy_points_ppr").alias("ppr_points"))

    required = ["rec", "rec_yds", "rec_td"]
    if not all(col in data_frame.columns for col in required):
        return data_frame

    return data_frame.with_columns(
        (
            pl.col("rec") * 1.0
            + pl.col("rec_yds") * 0.1
            + pl.col("rec_td") * 6.0
        ).alias("ppr_points")
    )


def add_lag_features(data_frame: pl.DataFrame) -> pl.DataFrame:
    """
    Add previous-week features per player.
    Find columns that ID player, season, and week.
    Sort by player/season/week, add "prev_week" versions of rec, rec_yds, and rec_td, etc.
    """
    player_col = _find_first_existing(data_frame.columns, ["player_id", "gsis_id", "player_name"])
    season_col = _find_first_existing(data_frame.columns, ["season"])
    week_col = _find_first_existing(data_frame.columns, ["week"])

    if not all([player_col, season_col, week_col]):
        raise ValueError("Missing player/season/week columns needed for lag features.")

    sort_cols = [player_col, season_col, week_col]
    data_frame = data_frame.sort(sort_cols)

    expressions = []
    for col in FEATURE_STATS:
        if col in data_frame.columns:
            safe = col.replace(".", "_")
            expressions.append(
                pl.col(col)
                .shift(1)
                .over(player_col)
                .alias(f"{safe}_prev_week")
            )

    return data_frame.with_columns(expressions)


def add_rolling_features(data_frame: pl.DataFrame) -> pl.DataFrame:
    """
    Add trailing averages over each player's last 3 and 5 games, ending with the
    game on that row. That game has already been played by the time of the game
    being predicted (the next one), so including it is not leakage, and leaving it
    out would ignore the most recent evidence. Assumes rows are sorted, which
    add_lag_features guarantees.
    """
    player_col = _find_first_existing(data_frame.columns, ["player_id", "gsis_id", "player_name"])
    if player_col is None:
        raise ValueError("Missing player identifier for rolling features.")

    expressions = []
    for col in FEATURE_STATS:
        if col in data_frame.columns:
            safe = col.replace(".", "_")
            expressions.append(
                pl.col(col)
                .rolling_mean(window_size=3, min_samples=1)
                .over(player_col)
                .alias(f"{safe}_rolling_3")
            )
            expressions.append(
                pl.col(col)
                .rolling_mean(window_size=5, min_samples=1)
                .over(player_col)
                .alias(f"{safe}_rolling_5")
            )

    out = data_frame.with_columns(expressions)
    return _add_trend_features(out)


def select_model_columns(
    data_frame: pl.DataFrame,
    extra_feature_cols: list[str] | None = None,
) -> pl.DataFrame:
    """
    Selects subset of columns that are needed for the model.
    """
    extra_feature_cols = extra_feature_cols or []
    # PPR first, then receptions / targets / yardage-style history, rolls grouped the same way.
    # temp/wind are deliberately absent: game-time weather isn't known before kickoff, and
    # nflverse leaves it null for upcoming and most indoor games.
    # is_home/is_dome/spread_line/total_line are also absent: on a training row they describe
    # the game just played, while serving would pass the next game's values, and betting lines
    # are often not posted yet. See ROADMAP.md for adding them back properly.
    meta_cols = [
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
    keep_if_exists = [
        *meta_cols,
        "ppr_points",
        "ppr_points_minus_roll3",
        *[f"{stat}_prev_week" for stat in FEATURE_STATS],
        *[f"{stat}_rolling_3" for stat in FEATURE_STATS],
        *[f"{stat}_rolling_5" for stat in FEATURE_STATS],
    ]
    keep = [col for col in keep_if_exists if col in data_frame.columns]
    for col in extra_feature_cols:
        if col in data_frame.columns and col not in keep:
            keep.append(col)
    keep.extend(col for col in map(next_week_column, PREDICTED_STATS) if col in data_frame.columns)
    return data_frame.select(keep)


def _add_trend_features(data_frame: pl.DataFrame) -> pl.DataFrame:
    """
    Simple momentum: latest game vs the trailing average that ends with it.
    """
    if "ppr_points" in data_frame.columns and "ppr_points_rolling_3" in data_frame.columns:
        return data_frame.with_columns(
            (pl.col("ppr_points") - pl.col("ppr_points_rolling_3")).alias("ppr_points_minus_roll3")
        )
    return data_frame


def _find_first_existing(columns: list[str], candidates: list[str]) -> str | None:
    """
    Utility to choose first available column name from set of candidates.
    """
    for col in candidates:
        if col in columns:
            return col
    return None