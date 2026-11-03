"""
Experiment: does scaling the inputs and tuning Ridge's alpha beat the current model?
Ridge's penalty depends on each input's scale, so unscaled rec_yds (0-200) and
target_share (0-1) are penalized very differently. Run from backend/:
  python experiments/scaling_compare.py
Read-only. Walks forward week by week, training only on games before each week, and
compares every variant on the same top 20 players, as the site scores them.

Result (2026-11-03): no variant beat the current model by more than the noise.
Over 2023-2025, the best (scaled, RidgeCV each week) moved ranking +0.005 +/- 0.006
and MAE -0.010 +/- 0.009; on 2026 weeks 2-8 it was -0.004 and +0.010. Season CV
picked alpha 316 every season. The current model stays.
"""
import sys
import warnings

sys.path.insert(0, ".")
warnings.filterwarnings("ignore")
import numpy as np
import polars as pl
from sklearn.linear_model import Ridge, RidgeCV
from sklearn.model_selection import GridSearchCV, LeaveOneGroupOut
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from wr_predictor import data_loader
from wr_predictor.dataset_builder import build_training_dataset
from wr_predictor.model import get_feature_columns

# Each player's games in order.
GAME_ORDER = ["player_id", "season", "week"]
SEASONS = list(range(2021, 2027))
TARGET = "next_week_ppr_points"
# Candidate penalties, from almost none to heavy.
ALPHAS = np.logspace(-2, 4, 13)

# Same rows the live model trains on: regular season, every WR game since 2021.
rows = build_training_dataset(seasons=SEASONS, min_games_for_player=0).filter(pl.col("season_type") == "REG")
base = get_feature_columns(rows)

# Each row's next game ("no" = season * 100 + week) and season-to-date points through
# this game, which decide that week's top 20, as in the other experiments.
wr = data_loader.load_player_weekly_stats(SEASONS).filter(pl.col("position") == "WR").sort(GAME_ORDER)
next_game = wr.with_columns(
    (pl.col("season").shift(-1).over("player_id") * 100 + pl.col("week").shift(-1).over("player_id")).alias("no")
).select(*GAME_ORDER, "no")
season_points = (
    wr.filter(pl.col("season_type") == "REG")
    .with_columns(pl.col("fantasy_points_ppr").cum_sum().over(["player_id", "season"]).alias("td"))
    .select(*GAME_ORDER, "td")
)
data = rows.join(next_game, on=GAME_ORDER, how="left").join(season_points, on=GAME_ORDER, how="left")
data = data.drop_nulls(subset=[*base, TARGET, "no", "td"])
print("rows", data.height, "features", len(base))


def tuned_alpha(season: int) -> float:
    """Best alpha for a test season, by leave-one-season-out MAE on earlier seasons only."""
    train = data.filter(pl.col("no") < season * 100)
    search = GridSearchCV(
        make_pipeline(StandardScaler(), Ridge()),
        {"ridge__alpha": ALPHAS},
        cv=LeaveOneGroupOut(),
        scoring="neg_mean_absolute_error",
    )
    search.fit(train.select(base).to_numpy(), train[TARGET].to_numpy(), groups=train["season"].to_numpy())
    return float(search.best_params_["ridge__alpha"])


def spear(actual, predicted) -> float:
    """Spearman rank correlation, 0 when undefined (every value tied)."""
    value = pl.DataFrame({"a": actual, "p": predicted}).select(pl.corr("a", "p", method="spearman")).item()
    return 0.0 if value is None or np.isnan(value) else value


def walk(seasons):
    """Score every variant on each week's top 20, training only on earlier games."""
    alphas = {season: tuned_alpha(season) for season in seasons}
    print("alpha tuned on earlier seasons:", alphas)
    out = []
    for cut in sorted(data["no"].unique().to_list()):
        season = cut // 100
        if season not in seasons:
            continue
        cohort = data.filter((pl.col("no") == cut) & (pl.col("season") == season)).sort("td", descending=True).head(20)
        if cohort.height < 15:
            continue
        train = data.filter(pl.col("no") < cut)
        variants = {
            "A current (unscaled, alpha 1)": Ridge(alpha=1.0),
            "B scaled, alpha 1": make_pipeline(StandardScaler(), Ridge(alpha=1.0)),
            "C scaled, alpha by season CV": make_pipeline(StandardScaler(), Ridge(alpha=alphas[season])),
            "D scaled, RidgeCV each week": make_pipeline(StandardScaler(), RidgeCV(alphas=ALPHAS)),
        }
        actual = cohort[TARGET].to_numpy()
        record = {"season": season}
        for name, model in variants.items():
            predicted = model.fit(train.select(base).to_numpy(), train[TARGET].to_numpy()).predict(cohort.select(base).to_numpy())
            record[f"{name}|rho"] = spear(actual, predicted)
            record[f"{name}|mae"] = float(np.abs(actual - predicted).mean())
        out.append(record)
    return out


def table(results, label):
    """Mean per-week ranking and MAE, with the paired change vs the current model."""
    print(f"\n{label}: {len(results)} weeks. Change vs current, paired by week (+/- standard error)")
    names = [k.split("|")[0] for k in results[0] if k.endswith("|rho")]
    for name in names:
        cells = []
        for metric in ("rho", "mae"):
            a = np.array([r[f"{names[0]}|{metric}"] for r in results])
            b = np.array([r[f"{name}|{metric}"] for r in results])
            d = b - a
            cells.append(f"{metric} {b.mean():.3f} ({d.mean():+.3f}+/-{d.std(ddof=1) / np.sqrt(len(d)):.3f})")
        print(f"  {name:32s} {'  '.join(cells)}")


table(walk((2023, 2024, 2025)), "Development 2023-2025")
table(walk((2026,)), "Confirmation 2026 so far")
