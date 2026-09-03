from __future__ import annotations

import polars as pl


def add_next_week_target(data_frame: pl.DataFrame) -> pl.DataFrame:
    """
    Create next week's fantasy output as the supervised-learning target.
    Requires ppr_points and player/season/week identifiers.
    Sorts by player/season/week, shifts ppr_points one week back
    Creates next_week_ppr_points column as next game's ppr_points.
    (for each player shifted -1 over each player)
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
            pl.col("ppr_points")
            .shift(-1)
            .over(player_col)
            .alias("next_week_ppr_points")
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