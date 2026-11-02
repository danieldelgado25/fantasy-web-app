"""Read-only: walk-forward test of each opportunity group on identical rows. Arg: features parquet."""
import sys
import warnings

sys.path.insert(0, ".")
warnings.filterwarnings("ignore")
import numpy as np
import polars as pl
from sklearn.linear_model import Ridge

from wr_predictor.model import get_feature_columns

rows = pl.read_parquet(sys.argv[1])
extras = [c for c in rows.columns if c.endswith(("_r3", "_r5"))] + ["vacated_share", "own_questionable", "own_missed_practice"]
base = [c for c in get_feature_columns(rows) if c not in extras and c not in ("ns", "nw", "nt", "td", "team_right", "team_targets", "vacated_share", "own_questionable", "own_missed_practice")]
print("base features", len(base))

GROUPS = {
    "A current": [],
    "B snap share": ["snap_pct_r3", "snap_pct_r5"],
    "C expected production": [c for c in extras if c.startswith(("receptions_exp", "rec_yards_gained_exp", "rec_touchdown_exp", "rec_fantasy_points_exp"))],
    "D red/end-zone & deep targets": [c for c in extras if c.startswith(("rz_", "gl_", "ez_", "deep_"))],
    "E ball quality (FTN)": [c for c in extras if c.startswith(("catchable", "contested"))],
    "F separation (NGS)": [c for c in extras if c.startswith(("avg_separation", "avg_cushion"))],
    "G drops & broken tackles": [c for c in extras if c.startswith(("drops", "broken"))],
    "H unused box score": [c for c in extras if c.startswith("receiving_")],
    "I team pass volume": ["team_targets_r5"],
    "J teammates ruled out": ["vacated_share"],
    "K own injury status": ["own_questionable", "own_missed_practice"],
}
GROUPS["N C + J"] = GROUPS["C expected production"] + GROUPS["J teammates ruled out"]
GROUPS["L C + D + J"] = GROUPS["C expected production"] + GROUPS["D red/end-zone & deep targets"] + GROUPS["J teammates ruled out"]
GROUPS["M all groups"] = sorted({c for v in GROUPS.values() for c in v})

coverage = {g: round(float(np.mean([rows.filter(pl.col("season") == 2026)[c].is_not_null().mean() for c in cols])), 3) for g, cols in GROUPS.items() if cols}
print("2026 coverage before filling:", coverage)

# Identical rows for every group: 2022 on (FTN starts then), regular season. Gaps get the column's
# average, since sparse sources such as NGS only list qualifying players.
data = rows.filter((pl.col("season_type") == "REG") & (pl.col("season") >= 2022)).with_columns((pl.col("ns") * 100 + pl.col("nw")).alias("no"))
data = data.with_columns([pl.col(c).fill_null(pl.col(c).mean()) for c in extras])
stats = ["ppr_points", "targets", "rec", "rec_td"]
targets = [f"next_week_{s}" for s in stats]
data = data.drop_nulls(subset=[*base, *targets, "no", "td"])
print("rows", data.height)


def spear(a, p):
    value = pl.DataFrame({"a": a, "p": p}).select(pl.corr("a", "p", method="spearman")).item()
    return 0.0 if value is None or np.isnan(value) else value


def walk(seasons):
    out = []
    for cut in sorted(data["no"].unique().to_list()):
        season = cut // 100
        if season not in seasons:
            continue
        cohort = data.filter((pl.col("no") == cut) & (pl.col("season") == season)).sort("td", descending=True).head(20)
        if cohort.height < 15:
            continue
        train = data.filter(pl.col("no") < cut)
        record = {"season": season, "week": cut % 100}
        for name, group in GROUPS.items():
            cols = base + group
            x_train, x_rows = train.select(cols).to_numpy(), cohort.select(cols).to_numpy()
            for stat in stats:
                actual = cohort[f"next_week_{stat}"].to_numpy()
                pred = Ridge(alpha=1.0).fit(x_train, train[f"next_week_{stat}"].to_numpy()).predict(x_rows)
                record[f"{name}|{stat}|rho"] = spear(actual, pred)
                record[f"{name}|{stat}|mae"] = float(np.abs(actual - pred).mean())
                if name == "A current" and stat == "ppr_points":
                    record["top5_miss"] = float((actual[:5] - pred[:5]).mean())
                    record["rest_miss"] = float((actual[5:] - pred[5:]).mean())
        out.append(record)
    return out


def table(results, label):
    print(f"\n{label}: {len(results)} weeks. Change vs current, paired by week (+/- standard error)")
    for name in GROUPS:
        cells = []
        for stat, short in (("ppr_points", "pts"), ("rec_td", "td"), ("targets", "tgt")):
            a = np.array([r[f"A current|{stat}|rho"] for r in results])
            b = np.array([r[f"{name}|{stat}|rho"] for r in results])
            d = b - a
            cells.append(f"{short} rank {b.mean():.3f} ({d.mean():+.3f}+/-{d.std(ddof=1) / np.sqrt(len(d)):.3f})")
        ma = np.array([r[f"A current|ppr_points|mae"] for r in results])
        mb = np.array([r[f"{name}|ppr_points|mae"] for r in results])
        dm = mb - ma
        print(f"  {name:30s} {'  '.join(cells)}  ptsMAE {mb.mean():.3f} ({dm.mean():+.3f}+/-{dm.std(ddof=1) / np.sqrt(len(dm)):.3f})")


def tiers(results, label):
    """Average actual minus predicted points for the top 5 by season points, then the rest."""
    for key in ("top5_miss", "rest_miss"):
        values = np.array([r[key] for r in results])
        print(f"  {label} {key}: {values.mean():+.2f} +/- {values.std(ddof=1) / np.sqrt(len(values)):.2f}")


dev = walk((2023, 2024, 2025))
table(dev, "Development 2023-2025")
print("\nPoints rank by season")
for name in GROUPS:
    print(f"  {name:30s} " + "  ".join(f"{s}: {np.mean([r[name + '|ppr_points|rho'] for r in dev if r['season'] == s]):.3f}" for s in (2023, 2024, 2025)))
current = walk((2026,))
table(current, "Confirmation 2026 so far")
print("Under-projection by tier (positive means players beat their projection)")
tiers(dev, "2023-2025")
for season in (2023, 2024, 2025):
    tiers([r for r in dev if r["season"] == season], str(season))
tiers(current, "2026")
