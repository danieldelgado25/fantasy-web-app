from __future__ import annotations

import polars as pl

# Box-score columns used to detect return-game activity (offense-free weeks we drop).
_SPECIAL_TEAMS_STAT_COLUMNS = [
    "kickoff_return_yards",
    "kickoff_return_tds",
    "punt_return_yards",
    "punt_return_tds",
    "lateral_return_yards",
    "lateral_return_tds",
]


def filter_wide_receivers(data_frame: pl.DataFrame) -> pl.DataFrame:
    """
    Filter the player stats dataframe to only include wide receivers.
    """
    return data_frame.filter(pl.col("position") == "WR")


def drop_special_teams_only_rows(data_frame: pl.DataFrame) -> pl.DataFrame:
    """
    Remove player-week rows where the only stat lines are special teams (returns),
    with no rushing or receiving usage. Pure zero-offense rows with no return
    stats are kept.
    """
    offensive_parts: list[pl.Expr] = []
    for col in ("targets", "rec", "receptions", "carries"):
        if col in data_frame.columns:
            offensive_parts.append(pl.col(col).fill_null(0))

    if not offensive_parts:
        return data_frame

    offensive = pl.sum_horizontal(offensive_parts) > 0

    st_parts = [
        pl.col(c).fill_null(0)
        for c in _SPECIAL_TEAMS_STAT_COLUMNS
        if c in data_frame.columns
    ]
    if not st_parts:
        return data_frame

    st_activity = pl.sum_horizontal(st_parts) > 0
    return data_frame.filter(offensive | ~st_activity)


def select_wr_columns(data_frame: pl.DataFrame) -> pl.DataFrame:
    """
    Select only the columns relevant for wide receiver analysis.
    Drops QB stats, FG stats, PAT stats, etc.
    """
    # Order: ids / game context, full-PPR fantasy, receiving volume then detail,
    # gadget rushing, laterals, return-game stats last.
    keep_columns = [
        "player_id",
        "player_name",
        "player_display_name",
        "position",
        "position_group",
        "headshot_url",
        "season",
        "week",
        "season_type",
        "game_id",
        "team",
        "opponent_team",
        "fantasy_points_ppr",
        "fantasy_points",
        "targets",
        "receptions",
        "receiving_yards",
        "receiving_tds",
        "receiving_fumbles",
        "receiving_fumbles_lost",
        "receiving_air_yards",
        "receiving_yards_after_catch",
        "receiving_first_downs",
        "receiving_epa",
        "receiving_2pt_conversions",
        "target_share",
        "air_yards_share",
        "wopr",
        "ryoe",
        "ryoe_perception",
        "adot",
        "ryoe_allowed",
        "ryoe_pass",
        "ryoe_run",
        "pacr",
        "racr",
        "carries",
        "rushing_yards",
        "rushing_tds",
        "rushing_fumbles",
        "rushing_fumbles_lost",
        "rushing_first_downs",
        "rushing_epa",
        "rushing_2pt_conversions",
        "lateral_receptions",
        "lateral_rush_yards",
        "lateral_rush_tds",
        "lateral_return_yards",
        "lateral_return_tds",
        "kickoff_return_yards",
        "kickoff_return_tds",
        "punt_return_yards",
        "punt_return_tds",
    ]
    existing_columns = [col for col in keep_columns if col in data_frame.columns]
    return data_frame.select(existing_columns)
