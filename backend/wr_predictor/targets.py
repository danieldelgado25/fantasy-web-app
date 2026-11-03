from __future__ import annotations

import polars as pl

from wr_predictor.features import GAME_ORDER, require_columns
from wr_predictor.stats import next_week_column, PREDICTED_STATS


def add_next_week_target(data_frame: pl.DataFrame) -> pl.DataFrame:
    """
    Create next game's value of each predicted stat as a supervised-learning target.
    Sorts each player's games, then shifts each stat back one game per player,
    giving next_week_ppr_points, next_week_targets, and so on. Like the lags, this
    crosses seasons: a season's final game is labeled with the player's next game,
    which may be a playoff game or the next season's opener.
    """
    require_columns(data_frame, [*GAME_ORDER, "ppr_points"], "target creation")

    return (
        data_frame.sort(GAME_ORDER)
        .with_columns(
            [
                pl.col(stat).shift(-1).over("player_id").alias(next_week_column(stat))
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