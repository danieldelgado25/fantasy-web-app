# Roadmap & Deferred Feature Notes

Design notes for decisions made and features intentionally deferred, so context isn't lost between sessions. Update this file when a deferred item is picked back up or a decision below changes.

## Deployment architecture

- **Frontend (React):** deploy to Vercel. Zero-config GitHub deploys, preview URLs per PR — a strong fit for a static/SSR React app.
- **Backend (Flask + `wr_predictor`):** deploy to a separate host built for long-running Python processes (Render or Railway are the leading candidates; not yet chosen). Reasoning: Vercel's Python support is serverless-function-only, with hard package-size limits that `scikit-learn` + `polars` + `nflreadpy` eat into, plus cold starts and short execution timeouts — a poor fit for a pipeline that pulls multi-season data and trains models. Data refresh/retraining should run as a scheduled batch job on the backend host, writing precomputed projections that the API serves — not something recomputed per-request.

## Deferred: rest-of-season (ROS) rankings

Not scheduled — needs a decision on approach before work starts. The current model only predicts one week ahead (`next_week_ppr_points`), so ROS isn't a free extension of it. Options, in increasing rigor:

1. **Chain the weekly model forward** — predict week N, feed that prediction into the rolling-average features, predict week N+1, repeat. Cheapest to build; error compounds each step out.
2. **New target variable** — e.g. `rest_of_season_avg_ppr`, trained directly rather than chained. More accurate, but is real modeling work: a new label in `targets.py` plus its own train/eval.
3. **Heuristic estimate** — project current usage metrics (target share, air yards) forward as a steady state, adjusted for schedule/byes. Fastest v1, least statistically rigorous.

Revisit once there's a clearer view on which trade-off is acceptable.

## Future feature: player news monitor

Not buildable yet — noted here so the design isn't lost before it's picked up.

**Goal:** when news breaks about a player (injury, role change, etc.), reflect its projected impact on that player's rankings — eventually automatically.

**Sketch:**
- **Ingestion:** a scheduled job polling news/injury sources (beat reporters, official injury reports, RSS/API feeds).
- **Impact scoring:** feed each item to an LLM with a structured prompt asking for a classification (severity, direction, confidence) rather than free text.
- **Applying it to projections — key design decision:** do *not* fold news sentiment into the trained model's features. The model's value is being a reproducible, leakage-free, stat-based forecast (see main [README.md](README.md)); mixing in sparse, hard-to-backtest LLM judgments would compromise that and make the model much harder to evaluate. Instead, apply news-driven adjustments as a **separate, clearly-labeled overlay** on top of the base projection (e.g. "base: 14.2 pts — flagged: questionable, hamstring, reported 9/2") rather than blending it into one number. Keeps the base model's integrity intact and the adjustment explainable.

This is its own project phase (ingestion + LLM classification + adjustment layer + UI surfacing), to be designed properly once the web app MVP and weekly rankings exist.
