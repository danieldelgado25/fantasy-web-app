"""Read-only: builds trailing opportunity features from nflverse into one scratch parquet. Arg: output path."""
import sys
import warnings

sys.path.insert(0, ".")
warnings.filterwarnings("ignore")
import nflreadpy as nfl
import polars as pl

from wr_predictor.dataset_builder import build_training_dataset

OUT = sys.argv[1]
SEASONS = list(range(2021, 2027))
KEY = ["player_id", "season", "week"]


def roll(frame, cols, windows=(3, 5)):
    """Trailing averages ending with each player's game on that row, matching the model's existing features."""
    frame = frame.sort("player_id", "season", "week")
    return frame.with_columns(
        [pl.col(c).rolling_mean(window_size=n, min_samples=1).over("player_id").alias(f"{c}_r{n}") for c in cols for n in windows]
    )


base = build_training_dataset(seasons=SEASONS, min_games_for_player=0)
stats_all = nfl.load_player_stats(SEASONS)
wr = stats_all.filter(pl.col("position") == "WR")
games = wr.select(KEY).unique()
print("base rows", base.height)

# Row key for the game each row predicts, plus season points so far.
keys = wr.sort(KEY).with_columns(
    pl.col("season").shift(-1).over("player_id").alias("ns"),
    pl.col("week").shift(-1).over("player_id").alias("nw"),
    pl.col("team").shift(-1).over("player_id").alias("nt"),
).select(*KEY, "ns", "nw", "nt", "team")
td = wr.filter(pl.col("season_type") == "REG").sort(KEY).with_columns(
    pl.col("fantasy_points_ppr").cum_sum().over(["player_id", "season"]).alias("td")
).select(*KEY, "td")

ids = nfl.load_ff_playerids().select(pl.col("pfr_id"), pl.col("gsis_id")).drop_nulls().unique(subset="pfr_id")

# Snap share.
snaps = nfl.load_snap_counts(SEASONS).join(ids, left_on="pfr_player_id", right_on="pfr_id").rename({"gsis_id": "player_id"})
snaps = roll(games.join(snaps.select(*KEY, pl.col("offense_pct").alias("snap_pct")), on=KEY, how="left"), ["snap_pct"])
print("snap coverage", snaps["snap_pct"].is_not_null().mean())

# Expected production from ffopportunity: what a player's targets were worth on average.
ff = nfl.load_ff_opportunity(SEASONS).with_columns(pl.col("season").cast(pl.Int32), pl.col("week").cast(pl.Int32))
print("ff columns with exp:", [c for c in ff.columns if "rec" in c and "exp" in c and "fantasy" in c] + [c for c in ff.columns if c.startswith("total_") and "exp" in c][:6])
ff_cols = ["receptions_exp", "rec_yards_gained_exp", "rec_touchdown_exp", "rec_fantasy_points_exp"]
ff = ff.select(*KEY, *[pl.col(c).cast(pl.Float64) for c in ff_cols])
exp = roll(games.join(ff, on=KEY, how="left"), ff_cols)
print("ff coverage", exp["rec_fantasy_points_exp"].is_not_null().mean())

# Target quality from play-by-play: red zone, end zone, deep, plus share of team red-zone targets.
pbp = nfl.load_pbp(SEASONS).filter((pl.col("pass_attempt") == 1) & pl.col("receiver_player_id").is_not_null() & (pl.col("two_point_attempt") == 0))
pbp = pbp.select("game_id", "play_id", "season", "week", "posteam", pl.col("receiver_player_id").alias("player_id"), "yardline_100", "air_yards")
print("pbp seasons", pbp.group_by("season").agg(pl.col("week").max()).sort("season").to_dicts())
target_kinds = pbp.with_columns(
    (pl.col("yardline_100") <= 20).cast(pl.Int32).alias("rz"),
    (pl.col("yardline_100") <= 10).cast(pl.Int32).alias("gl"),
    (pl.col("air_yards") >= pl.col("yardline_100")).fill_null(False).cast(pl.Int32).alias("ez"),
    (pl.col("air_yards") >= 20).fill_null(False).cast(pl.Int32).alias("deep"),
)
team_rz = target_kinds.group_by("season", "week", "posteam").agg(pl.col("rz").sum().alias("team_rz"))
by_player = target_kinds.group_by(KEY + ["posteam"]).agg(pl.col("rz").sum().alias("rz_tgt"), pl.col("gl").sum().alias("gl_tgt"), pl.col("ez").sum().alias("ez_tgt"), pl.col("deep").sum().alias("deep_tgt"))
by_player = by_player.join(team_rz, on=["season", "week", "posteam"]).with_columns((pl.col("rz_tgt") / pl.col("team_rz")).fill_nan(0).alias("rz_share"))
pbp_cols = ["rz_tgt", "gl_tgt", "ez_tgt", "deep_tgt", "rz_share"]
quality = roll(games.join(by_player.select(*KEY, *pbp_cols), on=KEY, how="left").with_columns(pl.col(pbp_cols).fill_null(0)), pbp_cols)

# Ball quality from FTN charting, 2022 on: how often a player's targets were catchable or contested.
ftn = nfl.load_ftn_charting(list(range(2022, 2027))).select(pl.col("nflverse_game_id").alias("game_id"), pl.col("nflverse_play_id").cast(pl.Float64).alias("play_id"), "is_catchable_ball", "is_contested_ball")
charted = pbp.join(ftn, on=["game_id", "play_id"]).group_by(KEY).agg(pl.col("is_catchable_ball").cast(pl.Float64).mean().alias("catchable"), pl.col("is_contested_ball").cast(pl.Float64).mean().alias("contested"))
print("ftn charted player-games", charted.height)
ball = roll(games.join(charted, on=KEY, how="left"), ["catchable", "contested"])

# Next Gen Stats: separation and cushion. NGS only lists qualifying players each week.
ngs = nfl.load_nextgen_stats(stat_type="receiving", seasons=SEASONS).filter(pl.col("week") > 0).select(pl.col("player_gsis_id").alias("player_id"), "season", "week", "avg_separation", "avg_cushion")
sep = roll(games.join(ngs, on=KEY, how="left"), ["avg_separation", "avg_cushion"])
print("ngs coverage", sep["avg_separation"].is_not_null().mean())

# PFR: drops and broken tackles.
pfr = nfl.load_pfr_advstats(seasons=SEASONS, stat_type="rec", summary_level="week").join(ids, left_on="pfr_player_id", right_on="pfr_id").rename({"gsis_id": "player_id"})
pfr = pfr.select(*KEY, pl.col("receiving_drop").cast(pl.Float64).alias("drops"), pl.col("receiving_broken_tackles").cast(pl.Float64).alias("broken"))
adv = roll(games.join(pfr, on=KEY, how="left"), ["drops", "broken"])

# Box-score columns already downloaded but unused.
box_cols = ["receiving_first_downs", "receiving_yards_after_catch", "receiving_epa"]
box = roll(wr.select(*KEY, *[pl.col(c).cast(pl.Float64) for c in box_cols]), box_cols)

# Team passing volume: all targets on the player's team, trailing 5 games.
team = stats_all.filter(pl.col("team").is_not_null()).group_by("season", "week", "team").agg(pl.col("targets").sum().cast(pl.Float64).alias("team_targets")).sort("team", "season", "week")
team = team.with_columns(pl.col("team_targets").rolling_mean(window_size=5, min_samples=1).over("team").alias("team_targets_r5"))

# Injury report for the game being predicted: own status, and target share of teammates ruled out.
inj = nfl.load_injuries(SEASONS).select("season", "week", "team", pl.col("gsis_id").alias("player_id"), "report_status", "practice_status").drop_nulls("player_id").unique(subset=KEY)
share = stats_all.filter(pl.col("target_share").is_not_null()).sort(KEY).with_columns(
    pl.col("target_share").rolling_mean(window_size=5, min_samples=1).over("player_id").alias("share_r5"),
    (pl.col("season") * 100 + pl.col("week")).alias("o"),
).select("player_id", "o", "share_r5")
out_list = inj.filter(pl.col("report_status") == "Out").with_columns((pl.col("season") * 100 + pl.col("week")).alias("o")).sort("o")
vacated = (
    out_list.join_asof(share.sort("o"), on="o", by="player_id", strategy="backward", allow_exact_matches=False)
    .group_by("season", "week", "team")
    .agg(pl.col("share_r5").fill_null(0).sum().alias("vacated_share"))
)

rows = base.join(keys, on=KEY, how="left").join(td, on=KEY, how="left")
for extra in (snaps, exp, quality, ball, sep, adv, box):
    rows = rows.join(extra.select(KEY + [c for c in extra.columns if c.endswith(("_r3", "_r5"))]), on=KEY, how="left")
rows = rows.join(team.select("season", "week", "team", "team_targets_r5"), on=["season", "week", "team"], how="left")
rows = rows.join(vacated, left_on=["ns", "nw", "nt"], right_on=["season", "week", "team"], how="left").with_columns(pl.col("vacated_share").fill_null(0.0))
own = inj.select(pl.col("season").alias("ns"), pl.col("week").alias("nw"), "player_id", "report_status", "practice_status")
rows = rows.join(own, on=["ns", "nw", "player_id"], how="left").with_columns(
    (pl.col("report_status") == "Questionable").fill_null(False).cast(pl.Int8).alias("own_questionable"),
    pl.col("practice_status").fill_null("").str.contains("Did Not").cast(pl.Int8).alias("own_missed_practice"),
).drop("report_status", "practice_status")
rows.write_parquet(OUT)
print("wrote", rows.height, "columns", len(rows.columns))
