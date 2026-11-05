from __future__ import annotations

import polars as pl

from wr_predictor.player_info import injury_report_statuses

"""
The injury news feed: every WR currently on the injury report or a reserve list,
newest change first. Display only, not a model input. nflverse's injury report and
weekly rosters carry no time stamps, so each run records when it first saw a status
by comparing with the previous run's feed.
"""

# Roster status for every reserve list. nflverse doesn't say which list (IR, PUP,
# NFI, ...), so all of them show as IR with a note saying so.
RESERVE_STATUS = "RES"
RESERVE_NOTE = "On a reserve list (IR, PUP or similar)"

# Worst to best, for ordering entries first seen at the same time.
SEVERITY = ["IR", "Out", "Doubtful", "DNP", "Questionable"]

# Columns of a feed entry, before first_seen is added.
ENTRY_COLUMNS = ["player_id", "player_name", "team", "week", "injury_status", "injury_note"]


def _latest_week(frame: pl.DataFrame, position: str) -> pl.DataFrame:
    """Rows for `position` in the latest week present. Empty in, empty out."""
    rows = frame.filter(pl.col("position") == position)
    if rows.is_empty():
        return rows
    return rows.filter(pl.col("week") == rows["week"].max())


def current_injury_news(injuries: pl.DataFrame, rosters: pl.DataFrame, position: str = "WR") -> pl.DataFrame:
    """
    Every player at `position` with a status right now, one row each (ENTRY_COLUMNS).
    Uses each source's latest week. A reserve list beats any report status, since the
    player can't play until activated. Healthy players are left out.
    """
    report = _latest_week(injuries, position)
    names = report.select(pl.col("gsis_id").alias("player_id"), pl.col("full_name").alias("player_name"), "team")
    from_report = (
        injury_report_statuses(report)
        .filter(pl.col("injury_status").is_not_null())
        .join(names, on="player_id")
        .select(ENTRY_COLUMNS)
    )

    reserve = (
        _latest_week(rosters, position)
        .filter((pl.col("status") == RESERVE_STATUS) & pl.col("gsis_id").is_not_null())
        .select(
            pl.col("gsis_id").alias("player_id"),
            pl.col("full_name").alias("player_name"),
            "team",
            "week",
            pl.lit("IR").alias("injury_status"),
            pl.lit(RESERVE_NOTE).alias("injury_note"),
        )
    )

    # Drop report entries for players already on a reserve list.
    from_report = from_report.join(reserve.select("player_id"), on="player_id", how="anti")
    return pl.concat([reserve, from_report], how="vertical_relaxed")


def carry_first_seen(current: pl.DataFrame, previous: pl.DataFrame | None, now: str) -> pl.DataFrame:
    """
    Add first_seen: the previous feed's time when a player's status hasn't changed,
    otherwise `now` (a UTC ISO time). Only the status counts, so a daily practice update
    under the same status isn't news. Sorted newest first, then worst status first.
    """
    with_seen = current.with_columns(pl.lit(now).alias("first_seen"))
    if previous is not None and not previous.is_empty():
        earlier = previous.select("player_id", "injury_status", pl.col("first_seen").alias("earlier_seen"))
        with_seen = (
            current.join(earlier, on=["player_id", "injury_status"], how="left")
            .with_columns(pl.coalesce("earlier_seen", pl.lit(now)).alias("first_seen"))
            .drop("earlier_seen")
        )
    # ISO times in one format sort correctly as text.
    severity = pl.col("injury_status").replace_strict(SEVERITY, list(range(len(SEVERITY))), default=len(SEVERITY))
    return with_seen.sort([pl.col("first_seen"), severity], descending=[True, False])
