from __future__ import annotations

import polars as pl

from wr_predictor.stats import next_week_column, PREDICTED_STATS


def add_next_week_target(data_frame: pl.DataFrame) -> pl.DataFrame:
    """
    Create next game's value of each predicted stat as a supervised-learning target.
    Requires ppr_points and player/season/week identifiers.
    Sorts by player/season/week, then shifts each stat back one game per player,
    giving next_week_ppr_points, next_week_targets, and so on.
    """
    player_col = _find_first_existing(data_frame.columns, ["player_id", "gsis_id", "player_name"])
    season_col = _find_first_existing(data_frame.columns, ["season"])
    week_col = _find_first_existing(data_frame.columns, ["week"])

    if not all([player_col, season_col, week_col]):
        raise ValueError("Missing player/season/week columns needed for target creation.")

    if "ppr_points" not in data_frame.columns:
        raise ValueError("ppr_points must exist before creating the target.")

    return (
        data_frame.sort([player_col, season_col, week_col])
        .with_columns(
            [
                pl.col(stat).shift(-1).over(player_col).alias(next_week_column(stat))
                for stat in PREDICTED_STATS
                if stat in data_frame.columns
            ]
        )
    )


def drop_rows_without_target(data_frame: pl.DataFrame) -> pl.DataFrame:
    """
    Removes rows where next_week_ppr_points is null.
    """
    return data_frame.filter(pl.col("next_week_ppr_points").is_not_null())


def _find_first_existing(columns: list[str], candidates: list[str]) -> str | None:
    """
    Utility to choose first available column name from set of candidates.
    """
    for col in candidates:
        if col in columns:
            return col
    return None