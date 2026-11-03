"""
Experiment: can touchdowns be projected better, and does that improve points?
Uses the features parquet from opportunity_build.py. Run from backend/:
  python experiments/touchdown_compare.py <features.parquet>
Read-only. Walks forward week by week, training only on games before each week, and
compares every variant on the same top 20 players.
"""
import sys
import warnings

sys.path.insert(0, ".")
warnings.filterwarnings("ignore")
import nflreadpy as nfl
import numpy as np
import polars as pl
from sklearn.linear_model import PoissonRegressor, Ridge
from sklearn.metrics import mean_poisson_deviance
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from wr_predictor.model import get_feature_columns

KEY = ["player_id", "season", "week"]
rows = pl.read_parquet(sys.argv[1])

# Touchdowns are rare, so a long window may tell more than the last 3-5 games.
stats = nfl.load_player_stats(list(range(2021, 2027))).filter(pl.col("position") == "WR").sort(KEY)
long_memory = stats.with_columns(
    pl.col("receiving_tds").cast(pl.Float64).rolling_sum(window_size=16, min_samples=4).over("player_id").alias("td_16"),
    pl.col("targets").cast(pl.Float64).rolling_sum(window_size=16, min_samples=4).over("player_id").alias("tgt_16"),
).with_columns((pl.col("td_16") / pl.col("tgt_16")).fill_nan(0.0).alias("td_per_target_16")).select(*KEY, "td_per_target_16", "td_16")
rows = rows.join(long_memory, on=KEY, how="left")

extras = [c for c in rows.columns if c.endswith(("_r3", "_r5"))] + ["vacated_share", "own_questionable", "own_missed_practice", "td_per_target_16", "td_16"]
skip = {"ns", "nw", "nt", "td", "team_right", "team_targets", *extras}
base = [c for c in get_feature_columns(rows) if c not in skip]
EXPECTED = [c for c in extras if c.startswith("rec_touchdown_exp")]
RED_ZONE = [c for c in extras if c.startswith(("rz_", "gl_", "ez_"))]
LONG = ["td_per_target_16", "td_16"]

data = rows.filter((pl.col("season_type") == "REG") & (pl.col("season") >= 2022)).with_columns((pl.col("ns") * 100 + pl.col("nw")).alias("no"))
data = data.with_columns([pl.col(c).fill_null(pl.col(c).mean()) for c in extras])
data = data.drop_nulls(subset=[*base, "next_week_rec_td", "next_week_ppr_points", "no", "td"])
data = data.with_columns((pl.col("next_week_ppr_points") - 6 * pl.col("next_week_rec_td")).alias("next_week_non_td"))
print("rows", data.height, "base features", len(base))

ridge = lambda: Ridge(alpha=1.0)
poisson = lambda: make_pipeline(StandardScaler(), PoissonRegressor(alpha=1.0, max_iter=500))
TD_VARIANTS = {
    "A current Ridge": (base, ridge),
    "B Ridge + long history": (base + LONG, ridge),
    "C Ridge + expected TDs": (base + EXPECTED, ridge),
    "D Ridge + red zone": (base + RED_ZONE, ridge),
    "E Ridge + all three": (base + LONG + EXPECTED + RED_ZONE, ridge),
    "F Poisson": (base, poisson),
    "G Poisson + all three": (base + LONG + EXPECTED + RED_ZONE, poisson),
}


def spear(a, p):
    value = pl.DataFrame({"a": a, "p": p}).select(pl.corr("a", "p", method="spearman")).item()
    return 0.0 if value is None or np.isnan(value) else float(value)


def walk(seasons):
    """Score each variant weekly. Points combine a non-touchdown model with 6 x projected touchdowns."""
    out = []
    for cut in sorted(data["no"].unique().to_list()):
        season = cut // 100
        if season not in seasons:
            continue
        cohort = data.filter((pl.col("no") == cut) & (pl.col("season") == season)).sort("td", descending=True).head(20)
        if cohort.height < 15:
            continue
        train = data.filter(pl.col("no") < cut)
        td_actual = cohort["next_week_rec_td"].to_numpy()
        pts_actual = cohort["next_week_ppr_points"].to_numpy()
        non_td = ridge().fit(train.select(base).to_numpy(), train["next_week_non_td"].to_numpy()).predict(cohort.select(base).to_numpy())
        direct = ridge().fit(train.select(base).to_numpy(), train["next_week_ppr_points"].to_numpy()).predict(cohort.select(base).to_numpy())
        record = {"season": season, "direct_rho": spear(pts_actual, direct), "direct_mae": float(np.abs(pts_actual - direct).mean())}
        for name, (cols, make) in TD_VARIANTS.items():
            pred = np.clip(make().fit(train.select(cols).to_numpy(), train["next_week_rec_td"].to_numpy()).predict(cohort.select(cols).to_numpy()), 1e-4, None)
            combined = non_td + 6 * pred
            record[name] = {
                "td_rho": spear(td_actual, pred),
                "td_mae": float(np.abs(td_actual - pred).mean()),
                "td_dev": float(mean_poisson_deviance(td_actual, pred)),
                "pts_rho": spear(pts_actual, combined),
                "pts_mae": float(np.abs(pts_actual - combined).mean()),
            }
        out.append(record)
    return out


def report(results, label):
    print(f"\n{label}: {len(results)} weeks")
    print(f"  Points from the current direct model: rank {np.mean([r['direct_rho'] for r in results]):.3f}, MAE {np.mean([r['direct_mae'] for r in results]):.3f}")
    a = {k: np.array([r["A current Ridge"][k] for r in results]) for k in ("td_rho", "td_dev")}
    direct_rho = np.array([r["direct_rho"] for r in results])
    direct_mae = np.array([r["direct_mae"] for r in results])
    for name in TD_VARIANTS:
        rho = np.array([r[name]["td_rho"] for r in results])
        dev = np.array([r[name]["td_dev"] for r in results])
        pts = np.array([r[name]["pts_rho"] for r in results])
        mae = np.array([r[name]["pts_mae"] for r in results])
        d, e, m = rho - a["td_rho"], pts - direct_rho, mae - direct_mae
        se = lambda x: x.std(ddof=1) / np.sqrt(len(x))
        print(
            f"  {name:24s} TD rank {rho.mean():.3f} ({d.mean():+.3f}+/-{se(d):.3f})  TD deviance {dev.mean():.4f}"
            f"  | points rank {pts.mean():.3f} ({e.mean():+.3f}+/-{se(e):.3f})  points MAE {mae.mean():.3f} ({m.mean():+.3f}+/-{se(m):.3f})"
        )


dev_results = walk((2023, 2024, 2025))
report(dev_results, "Development 2023-2025")
print("\nTD rank by season")
for name in TD_VARIANTS:
    print(f"  {name:24s} " + "  ".join(f"{s}: {np.mean([r[name]['td_rho'] for r in dev_results if r['season'] == s]):.3f}" for s in (2023, 2024, 2025)))
report(walk((2026,)), "Confirmation 2026 so far")
