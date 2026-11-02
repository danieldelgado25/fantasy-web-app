from __future__ import annotations

from datetime import datetime
from pathlib import Path

import polars as pl

from wr_predictor.stats import PREDICTED_STATS

"""
The prediction log. Predictions are saved before kickoff, so they can be compared
with actual results afterwards.
"""

# Columns that identify a logged prediction.
LOG_KEY = ["season", "week", "player_id"]


def season_points(stats: pl.DataFrame, season: int) -> pl.DataFrame:
    """
    Official regular-season PPR totals per player for `season`, from games already in
    `stats`. Falls back to the previous season before any games have been played.
    Rounded because float sums vary with row order, which would randomly break exact ties.
    """
    regular = stats.filter(pl.col("season_type") == "REG")
    played = regular.filter(pl.col("season") == season)
    if played.is_empty():
        played = regular.filter(pl.col("season") == season - 1)
    return played.group_by("player_id").agg(pl.col("fantasy_points_ppr").sum().round(2).alias("season_points"))


def add_rank(frame: pl.DataFrame, points: pl.DataFrame) -> pl.DataFrame:
    """
    Rank players best-first by season points. Players with none rank last. Sorting
    by player_id first makes tied ranks repeatable, so reruns don't change the output.
    """
    return (
        frame.join(points, on="player_id", how="left")
        .with_columns(pl.col("season_points").fill_null(0.0))
        .sort("player_id")
        .with_columns(pl.col("season_points").rank(method="ordinal", descending=True).cast(pl.Int32).alias("rank"))
    )


def build_log_rows(ranked: pl.DataFrame) -> pl.DataFrame:
    """
    Reduce ranked predictions to the columns worth keeping. Stores each stat's
    baseline, the average of the last 3 games, so it is frozen with the prediction.
    Also stores season points, which decide who is in that week's scored top players.
    """
    return ranked.select(
        *LOG_KEY,
        pl.col("player_display_name").alias("player_name"),
        "team",
        "opponent_team",
        "rank",
        pl.col("season_points").round(2),
        *[pl.col(f"pred_{stat}").round(2) for stat in PREDICTED_STATS],
        *[pl.col(f"{stat}_rolling_3").round(2).alias(f"base_{stat}") for stat in PREDICTED_STATS],
    )


def not_yet_kicked_off(frame: pl.DataFrame, now_eastern: datetime) -> pl.DataFrame:
    """
    Keep rows whose game hasn't started. nflverse schedule times are US Eastern, so
    `now_eastern` must be too. A missing or unreadable time is kept rather than dropped.
    """
    kickoff = (pl.col("gameday") + " " + pl.col("gametime")).str.to_datetime("%Y-%m-%d %H:%M", strict=False)
    return frame.filter(kickoff.is_null() | (kickoff > now_eastern))


def upsert_log(path: str, rows: pl.DataFrame) -> pl.DataFrame:
    """
    Write `rows` into the log at `path`, replacing any earlier prediction for the
    same player and game. Other rows are left alone, so as long as callers only pass
    games that haven't kicked off, a logged prediction can't change after kickoff.
    """
    log_path = Path(path)
    if log_path.exists():
        rows = pl.concat([pl.read_csv(log_path, schema=rows.schema).join(rows, on=LOG_KEY, how="anti"), rows])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    rows = rows.sort(LOG_KEY)
    rows.write_csv(log_path)
    return rows
