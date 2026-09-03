from __future__ import annotations

import polars as pl


def add_basic_fantasy_points(data_frame: pl.DataFrame) -> pl.DataFrame:
    """
    Add PPR fantasy points if enough receiving columns exist.
    If data_frame has rec, rec_yds, and rec_td columns, add a ppr_points column:
    1 point per reception, 0.1 points per yard, 6 points per touchdown.
    """
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

    lag_candidates = [
        "ppr_points",
        "rec",
        "targets",
        "rec_yds",
        "rec_td",
        "target_share",
        "air_yards_share",
        "wopr",
        "receiving_air_yards",
    ]

    expressions = []
    for col in lag_candidates:
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
    Add simple trailing rolling averages.
    For ppr_points, targets, and rec_yds, add rolling averages over the past 3 and 5 weeks.
    """
    player_col = _find_first_existing(data_frame.columns, ["player_id", "gsis_id", "player_name"])
    if player_col is None:
        raise ValueError("Missing player identifier for rolling features.")

    rolling_candidates = [
        "ppr_points",
        "targets",
        "rec_yds",
        "target_share",
        "air_yards_share",
        "wopr",
        "receiving_air_yards",
    ]

    expressions = []
    for col in rolling_candidates:
        if col in data_frame.columns:
            safe = col.replace(".", "_")
            expressions.append(
                pl.col(col)
                .shift(1)
                .rolling_mean(window_size=3, min_samples=1)
                .over(player_col)
                .alias(f"{safe}_rolling_3")
            )
            expressions.append(
                pl.col(col)
                .shift(1)
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
    target_col = "next_week_ppr_points"
    # PPR first, then receptions / targets / yardage-style history, rolls grouped the same way.
    keep_if_exists = [
        "player_id",
        "player_name",
        "player_display_name",
        "season",
        "week",
        "season_type",
        "team",
        "opponent_team",
        "home_away",
        "is_home",
        "is_dome",
        "spread_line",
        "total_line",
        "temp",
        "wind",
        "ppr_points",
        "ppr_points_prev_week",
        "ppr_points_minus_roll3",
        "rec_prev_week",
        "targets_prev_week",
        "rec_yds_prev_week",
        "rec_td_prev_week",
        "target_share_prev_week",
        "air_yards_share_prev_week",
        "wopr_prev_week",
        "receiving_air_yards_prev_week",
        "ppr_points_rolling_3",
        "ppr_points_rolling_5",
        "rec_yds_rolling_3",
        "rec_yds_rolling_5",
        "targets_rolling_3",
        "targets_rolling_5",
        "target_share_rolling_3",
        "target_share_rolling_5",
        "air_yards_share_rolling_3",
        "air_yards_share_rolling_5",
        "wopr_rolling_3",
        "wopr_rolling_5",
        "receiving_air_yards_rolling_3",
        "receiving_air_yards_rolling_5",
    ]
    keep = [col for col in keep_if_exists if col in data_frame.columns]
    for col in extra_feature_cols:
        if col in data_frame.columns and col not in keep:
            keep.append(col)
    if target_col in data_frame.columns:
        keep.append(target_col)
    return data_frame.select(keep)


def _add_trend_features(data_frame: pl.DataFrame) -> pl.DataFrame:
    """
    Simple momentum: last game vs trailing rolling mean (no current-week leakage).
    """
    if (
        "ppr_points_prev_week" in data_frame.columns
        and "ppr_points_rolling_3" in data_frame.columns
    ):
        return data_frame.with_columns(
            (
                pl.col("ppr_points_prev_week") - pl.col("ppr_points_rolling_3")
            ).alias("ppr_points_minus_roll3")
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