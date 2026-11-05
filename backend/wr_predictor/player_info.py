from __future__ import annotations

import polars as pl

from wr_predictor.stats import NEUTRAL_TOTAL_LINE

"""
Display-only player details for the website: bio, headshot, team logo and
season-to-date stats. Nothing here feeds the model or the prediction log.
"""

# nflreadpy player columns shown on the site, renamed to the names the site uses.
PROFILE_COLUMNS = {
    "gsis_id": "player_id",
    "headshot": "headshot_url",
    "jersey_number": "jersey_number",
    "birth_date": "birth_date",
    "height": "height_inches",
    "weight": "weight_lbs",
    "college_name": "college",
    "years_of_experience": "years_exp",
}

# Season-to-date totals shown on the site, keyed by weekly stats column.
SEASON_STAT_COLUMNS = {
    "targets": "season_targets",
    "receptions": "season_rec",
    "receiving_yards": "season_rec_yds",
    "receiving_tds": "season_rec_td",
}

# The upcoming game as the model saw it, renamed for the site. These are the model's own
# next_* inputs, so the matchup shown is exactly what the projection was based on.
GAME_CONTEXT_COLUMNS = {
    "next_is_home": "is_home",
    "next_is_dome": "is_dome",
    "next_total_line": "game_total",
    "next_implied_total": "team_implied_total",
    "gameday": "gameday",
    "gametime": "gametime",
}


def game_context(ranked: pl.DataFrame) -> pl.DataFrame:
    """
    One row per player with their upcoming game's details, plus line_posted. Before a
    betting line is posted the model uses a neutral stand-in total, which the site
    shouldn't show as a real line.
    """
    # ponytail: detects the stand-in by value. Safe because real totals move in half
    # points and the stand-in (44.7) doesn't; carry a flag from the schedule if that changes.
    return ranked.select(
        "player_id",
        *[pl.col(src).alias(dst) for src, dst in GAME_CONTEXT_COLUMNS.items()],
        (pl.col("next_total_line") != NEUTRAL_TOTAL_LINE).alias("line_posted"),
    )


def defense_vs_wr(stats: pl.DataFrame, season: int) -> pl.DataFrame:
    """
    PPR points each defense has allowed to WRs per game in `season`'s regular season,
    and its rank among defenses: 1 allows the most, so it is the easiest matchup.
    Display only, not a model input: a few games against uneven receiver groups make
    it too noisy to trust, so the projection doesn't use it. Keyed by opponent_team,
    so it joins straight onto each player's upcoming opponent.
    """
    played = stats.filter((pl.col("season") == season) & (pl.col("season_type") == "REG"))
    # Total WR points per defense per game first, so games with more WRs aren't averaged down.
    per_game = played.group_by("opponent_team", "week").agg(pl.col("fantasy_points_ppr").sum())
    return (
        per_game.group_by("opponent_team")
        .agg(pl.col("fantasy_points_ppr").mean().round(2).alias("opp_wr_points_allowed"))
        .with_columns(
            pl.col("opp_wr_points_allowed").rank("min", descending=True).cast(pl.Int32).alias("opp_wr_allowed_rank")
        )
    )

# Practice wording in the injury report, shortened for the site's note.
PRACTICE_LABELS = {
    "Did Not Participate In Practice": "Did not practice",
    "Limited Participation in Practice": "Limited practice",
    "Full Participation in Practice": "Full practice",
}


def add_injury_status(rows: pl.DataFrame, injuries: pl.DataFrame) -> pl.DataFrame:
    """
    Add injury_status, the worst status for the game being projected, and injury_note,
    its details (e.g. "Questionable · Did not practice · Hamstring"). Worst to best:
    Out, Doubtful, DNP (did not practice, for an injury), Questionable. Limited or full practice with
    no game status, or no report at all, leaves both null: healthy. IR isn't set here:
    IR players are already off the site, dropped by the active roster filter.
    Matched on the projected season and week, so an old report never carries over.
    Display only, not a model input.
    """
    report = injuries.select(
        pl.col("gsis_id").alias("player_id"),
        "season",
        "week",
        "report_status",
        pl.col("practice_status").replace_strict(PRACTICE_LABELS, default=None).alias("practice"),
        pl.coalesce("report_primary_injury", "practice_primary_injury").alias("injury"),
    )
    # The when-chain order is the worst-to-best order: the first match wins.
    status = (
        pl.when(pl.col("report_status").is_in(["Out", "Doubtful"]))
        .then(pl.col("report_status"))
        # A veteran rest day or personal reason isn't an injury, so it doesn't count as DNP.
        .when(
            (pl.col("practice") == PRACTICE_LABELS["Did Not Participate In Practice"])
            & ~pl.col("injury").fill_null("").str.starts_with("Not injury related")
        )
        .then(pl.lit("DNP"))
        .when(pl.col("report_status") == "Questionable")
        .then(pl.lit("Questionable"))
    )
    note = pl.concat_str(["report_status", "practice", "injury"], separator=" · ", ignore_nulls=True)
    flagged = report.with_columns(status.alias("injury_status")).with_columns(
        pl.when(pl.col("injury_status").is_not_null()).then(note).alias("injury_note")
    )
    return rows.join(
        flagged.select("player_id", "season", "week", "injury_status", "injury_note"),
        on=["player_id", "season", "week"],
        how="left",
    )


def player_profiles(players: pl.DataFrame) -> pl.DataFrame:
    """One row of bio details per player, from nflreadpy's player table."""
    return players.select([pl.col(src).alias(dst) for src, dst in PROFILE_COLUMNS.items()]).unique("player_id")


def season_totals(stats: pl.DataFrame, season: int) -> pl.DataFrame:
    """Regular-season games played and receiving totals per player for `season` so far."""
    played = stats.filter((pl.col("season") == season) & (pl.col("season_type") == "REG"))
    return played.group_by("player_id").agg(
        pl.len().cast(pl.Int32).alias("season_games"),
        *[pl.col(src).sum().alias(dst) for src, dst in SEASON_STAT_COLUMNS.items()],
    )


def add_player_info(rows: pl.DataFrame, players: pl.DataFrame, teams: pl.DataFrame, stats: pl.DataFrame, season: int) -> pl.DataFrame:
    """
    Attach profiles, season totals and team logo to projection rows. Left joins, so a
    player missing from any source keeps their projection with empty details.
    """
    logos = teams.select(pl.col("team_abbr").alias("team"), pl.col("team_logo_espn").alias("team_logo_url"))
    return (
        rows.join(player_profiles(players), on="player_id", how="left")
        .join(season_totals(stats, season), on="player_id", how="left")
        .join(logos, on="team", how="left")
    )
