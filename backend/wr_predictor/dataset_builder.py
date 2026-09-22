from __future__ import annotations

import os
import polars as pl

from wr_predictor import data_loader, features, filters, targets

"""
File imported by main.py to build the training dataset.
Pulls data using data_loader.py, Filters to WRs using filters.py,
Adds fantasy points using features.py, created targets using targets.py,
Writes final dataset to a CSV file and returns the Polars DataFrame.
"""


def build_training_dataset(
    seasons: list[int],
    min_games_for_player: int = 4,
    output_path: str | None = None,
    position: str = "WR",
    merge_ff_opportunity: bool = False,
) -> pl.DataFrame:
    """
    Build the WR training dataset: load stats, filter to position, add features
    and next-week target, apply min-games filter, optionally write CSV.
    """
    # Load weekly stats and player metadata
    weekly = data_loader.load_player_weekly_stats(seasons)
    players = data_loader.load_players()

    # Normalize column names from nflreadpy (receptions, receiving_yards, receiving_tds) to our names
    weekly = _normalize_receiving_columns(weekly)

    # Game context from schedules (spread, total, home flag) — all known before kickoff
    weekly = _merge_schedule_context(weekly, seasons)

    # Filter to position (WR): join with players if position not in weekly
    player_col = _find_first_existing(weekly.columns, ["player_id", "gsis_id"])
    if player_col is None:
        raise ValueError("Weekly stats must have player_id or gsis_id.")
    if "position" not in weekly.columns and not players.is_empty():
        pos_col = _find_first_existing(players.columns, ["position", "pos"])
        id_in_players = _find_first_existing(players.columns, ["player_id", "gsis_id"])
        if pos_col and id_in_players:
            players = players.select([id_in_players, pos_col]).unique()
            if pos_col != "position":
                players = players.rename({pos_col: "position"})
            weekly = weekly.join(
                players,
                left_on=player_col,
                right_on=id_in_players,
                how="inner",
            )
    if "position" in weekly.columns:
        weekly = weekly.filter(pl.col("position") == position)

    weekly = filters.drop_special_teams_only_rows(weekly)

    # PPR fantasy points, then target and drop rows without target
    weekly = features.add_basic_fantasy_points(weekly)
    weekly = targets.add_next_week_target(weekly)
    weekly = targets.drop_rows_without_target(weekly)

    # Optional min games per player per season.
    # This can be used to restrict the training set, but is disabled
    # when min_games_for_player is 0 or None so that we avoid
    # discarding potentially informative rows.
    season_col = _find_first_existing(weekly.columns, ["season"])
    if season_col and min_games_for_player and min_games_for_player > 0:
        game_counts = (
            weekly.group_by([player_col, season_col])
            .agg(pl.len().alias("_games"))
            .filter(pl.col("_games") >= min_games_for_player)
        )
        weekly = weekly.join(
            game_counts.select([player_col, season_col]),
            on=[player_col, season_col],
            how="inner",
        )

    # Lag and rolling features, then model columns
    weekly = features.add_lag_features(weekly)
    weekly = features.add_rolling_features(weekly)

    ff_extra_cols: list[str] = []
    if merge_ff_opportunity:
        weekly, ff_extra_cols = _merge_ff_opportunity(weekly, seasons)

    weekly = features.select_model_columns(weekly, extra_feature_cols=ff_extra_cols)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        weekly.write_csv(output_path)

    return weekly


def build_latest_snapshot(
    seasons: list[int],
    position: str = "WR",
    merge_ff_opportunity: bool = False,
    output_path: str | None = None,
) -> pl.DataFrame:
    """
    Build one row per player: their most recent game's feature values, with
    no next_week_ppr_points (it hasn't been played yet). This is the row
    build_training_dataset always drops, because training needs a known
    target — inference needs exactly that dropped row. Mirrors
    build_training_dataset's pipeline up through feature creation, then
    diverges: keep the latest row per player instead of filtering by target.
    No min_games_for_player filter here on purpose — a live projection
    should still be produced for a rookie or a player back from injury
    who wouldn't clear a minimum-games bar this season.
    """
    weekly = data_loader.load_player_weekly_stats(seasons)
    players = data_loader.load_players()

    weekly = _normalize_receiving_columns(weekly)
    weekly = _merge_schedule_context(weekly, seasons)

    player_col = _find_first_existing(weekly.columns, ["player_id", "gsis_id"])
    if player_col is None:
        raise ValueError("Weekly stats must have player_id or gsis_id.")
    if "position" not in weekly.columns and not players.is_empty():
        pos_col = _find_first_existing(players.columns, ["position", "pos"])
        id_in_players = _find_first_existing(players.columns, ["player_id", "gsis_id"])
        if pos_col and id_in_players:
            players = players.select([id_in_players, pos_col]).unique()
            if pos_col != "position":
                players = players.rename({pos_col: "position"})
            weekly = weekly.join(
                players,
                left_on=player_col,
                right_on=id_in_players,
                how="inner",
            )
    if "position" in weekly.columns:
        weekly = weekly.filter(pl.col("position") == position)

    weekly = filters.drop_special_teams_only_rows(weekly)
    weekly = features.add_basic_fantasy_points(weekly)
    weekly = targets.add_next_week_target(weekly)
    weekly = features.add_lag_features(weekly)
    weekly = features.add_rolling_features(weekly)

    ff_extra_cols: list[str] = []
    if merge_ff_opportunity:
        weekly, ff_extra_cols = _merge_ff_opportunity(weekly, seasons)

    season_col = _find_first_existing(weekly.columns, ["season"])
    week_col = _find_first_existing(weekly.columns, ["week"])
    latest = (
        weekly.sort([player_col, season_col, week_col])
        .group_by(player_col, maintain_order=True)
        .last()
    )

    latest = features.select_model_columns(latest, extra_feature_cols=ff_extra_cols)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        latest.write_csv(output_path)

    return latest


def attach_next_game_context(snapshot: pl.DataFrame, seasons: list[int]) -> pl.DataFrame:
    """
    Replace a snapshot's game-context columns (opponent_team, season, week,
    is_home, is_dome, spread_line, total_line) with the player's team's next
    scheduled game in `seasons`, instead of the last-played game's context
    build_latest_snapshot otherwise carries forward. Without this, a snapshot
    taken after a playoff run reports that playoff opponent as the "next"
    matchup, which is wrong the moment a new season starts. `seasons` should
    cover whatever season the upcoming game falls in (not necessarily the
    same seasons the snapshot's stats were built from).
    Drops any player whose team has no remaining scheduled game in `seasons`.
    """
    required = {"player_id", "team", "season", "week"}
    if not required.issubset(snapshot.columns):
        return snapshot

    sched = data_loader.load_schedules(seasons)
    if sched.is_empty():
        return snapshot.clear()

    keep = [c for c in ("season", "week", "home_team", "away_team", "spread_line", "total_line", "roof", "temp", "wind") if c in sched.columns]
    sched = sched.select(keep)

    home_view = sched.rename({"home_team": "team", "away_team": "opponent_team"}).with_columns(pl.lit(1).cast(pl.Int8).alias("is_home"))
    away_view = sched.rename({"away_team": "team", "home_team": "opponent_team"}).with_columns(pl.lit(0).cast(pl.Int8).alias("is_home"))
    team_schedule = pl.concat([home_view, away_view], how="diagonal_relaxed")

    if "roof" in team_schedule.columns:
        roof_str = pl.col("roof").cast(pl.Utf8).fill_null("")
        team_schedule = team_schedule.with_columns(
            roof_str.str.to_lowercase().str.contains("dome").cast(pl.Int8).alias("is_dome")
        ).drop("roof")

    team_schedule = team_schedule.rename({"season": "next_season", "week": "next_week"})

    stale_cols = [c for c in ("opponent_team", "spread_line", "total_line", "is_home", "is_dome", "temp", "wind") if c in snapshot.columns]
    anchor = snapshot.drop(stale_cols).rename({"season": "last_season", "week": "last_week"})

    joined = anchor.join(team_schedule, on="team", how="left")
    joined = joined.filter(
        (pl.col("next_season") > pl.col("last_season"))
        | ((pl.col("next_season") == pl.col("last_season")) & (pl.col("next_week") > pl.col("last_week")))
    )
    joined = (
        joined.sort(["player_id", "next_season", "next_week"])
        .group_by("player_id", maintain_order=True)
        .first()
    )

    return joined.drop(["last_season", "last_week"]).rename({"next_season": "season", "next_week": "week"})


def _normalize_receiving_columns(data_frame: pl.DataFrame) -> pl.DataFrame:
    """Rename nflreadpy receiving columns to rec, rec_yds, rec_td if present."""
    renames = {}
    if "receptions" in data_frame.columns and "rec" not in data_frame.columns:
        renames["receptions"] = "rec"
    if "receiving_yards" in data_frame.columns and "rec_yds" not in data_frame.columns:
        renames["receiving_yards"] = "rec_yds"
    if "receiving_tds" in data_frame.columns and "rec_td" not in data_frame.columns:
        renames["receiving_tds"] = "rec_td"
    if renames:
        return data_frame.rename(renames)
    return data_frame


def _find_first_existing(columns: list[str], candidates: list[str]) -> str | None:
    for col in candidates:
        if col in columns:
            return col
    return None


def _merge_ff_opportunity(weekly: pl.DataFrame, seasons: list[int]) -> tuple[pl.DataFrame, list[str]]:
    """
    Join ffopportunity / expected fantasy metrics when available (ffverse data via nflreadpy).
    Returns the frame and the list of joined numeric feature column names.
    """
    if weekly.is_empty():
        return weekly, []

    try:
        ff = data_loader.load_ff_opportunity(seasons)
    except Exception:
        return weekly, []

    if ff.is_empty():
        return weekly, []

    join_keys = [k for k in ("player_id", "season", "week") if k in ff.columns and k in weekly.columns]
    if len(join_keys) < 3:
        return weekly, []

    # ff_opportunity returns season as a string and week as a float, while
    # weekly's are both int. Align dtypes to weekly's before joining, or
    # polars raises a SchemaError on the key dtype mismatch.
    ff = ff.with_columns(
        [pl.col(key).cast(weekly.schema[key]) for key in ("season", "week") if key in ff.columns]
    )

    numeric_cols: list[str] = []
    for col in ff.columns:
        if col in join_keys:
            continue
        dtype = ff.schema[col]
        is_num = getattr(dtype, "is_numeric", lambda: False)()
        if is_num:
            numeric_cols.append(col)

    preferred = [
        c
        for c in numeric_cols
        if any(s in c.lower() for s in ("fantasy", "expected", "x_", "xp_", "proj", "opportunity"))
    ]
    pick = preferred[:8] if preferred else numeric_cols[:8]
    if not pick:
        return weekly, []

    joined = weekly.join(ff.select(join_keys + pick), on=join_keys, how="left")
    return joined, pick


def _merge_schedule_context(weekly: pl.DataFrame, seasons: list[int]) -> pl.DataFrame:
    """
    Join nflverse schedule fields by game_id for pre-game situational features.
    """
    if weekly.is_empty() or "game_id" not in weekly.columns:
        return weekly

    try:
        sched = data_loader.load_schedules(seasons)
    except Exception:
        return weekly

    if sched.is_empty() or "game_id" not in sched.columns:
        return weekly

    sched_cols = [
        c
        for c in (
            "game_id",
            "home_team",
            "away_team",
            "spread_line",
            "total_line",
            "roof",
            "surface",
            "temp",
            "wind",
        )
        if c in sched.columns
    ]
    sched_small = sched.select(sched_cols).unique(subset=["game_id"], keep="first")
    out = weekly.join(sched_small, on="game_id", how="left")

    if "team" in out.columns and "home_team" in out.columns:
        out = out.with_columns(
            (pl.col("team") == pl.col("home_team")).cast(pl.Int8).alias("is_home")
        )
    if "roof" in out.columns:
        roof_str = pl.col("roof").cast(pl.Utf8).fill_null("")
        out = out.with_columns(
            roof_str.str.to_lowercase().str.contains("dome").cast(pl.Int8).alias("is_dome")
        )

    return out