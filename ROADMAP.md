# Roadmap & Deferred Feature Notes

Design notes for decisions made and features intentionally deferred, so context isn't lost between sessions. Update this file when a deferred item is picked back up or a decision below changes.

## Phases to deployment

Check items off as they land. Deployment waits on Phase 5, because proving the predictions comes before publishing them.

### Phase 1: Deployment readiness (done)
- [x] Fix the API start command, stale seasons and projection errors
- [x] Use rosters and each team's next unplayed game
- [x] Pin dependencies and stop mock data reaching production

### Phase 2: Prediction pipeline (done)
- [x] Official PPR points, and shared stat groups for future positions
- [x] One model per stat, with a corrected last-3-games baseline
- [x] Prediction log, scoring, the passing bar and a season replay
- [x] Top 20 table and a static projections file

### Phase 3: Start live logging (deadline: before the Nov 5 kickoff)
- [x] Push `deploy-readiness`
- [x] Merge it to `main`
- [ ] Run the refresh workflow by hand from the GitHub Actions tab, or wait for the 10:00 UTC run
- [ ] Confirm its commit updated `backend/predictions/2026.csv` and `projections.json`
- [ ] Confirm the next scheduled daily run works

Done when: week 9 predictions are on GitHub before kickoff and the daily job runs unattended.

### Phase 4: CI
- [x] Run backend tests, the frontend type check and the build on every push
- [x] Push a deliberately failing branch to prove CI catches it
- [x] Decide how to enforce CI: not yet, revisited in Phase 6
- [x] Write down what to do when CI or the daily job fails (see "When something fails")

Done when: every push is checked and failures are visible. For now, merge only after a green check.

### Phase 5: Prove the model (weeks 9-12 live, first verdict after Nov 30)
- [ ] Review each finished week: predicted vs actual targets, catches and points
- [x] Replace the fixed 0.30 ranking bar with beating the baseline's ranking
- [x] Add next-game context back, with training and serving using the same game
- [ ] Test past-error features and other model types, keeping only what beats the current model
- [ ] Pass the bar on four finished live weeks: 20 of 20 predictions, and better than the baseline on both MAE and ranking

Done when: `backend/predictions/2026_report.json` shows the live gate passed. A model change restarts the four-week window, so week 15 is the last week a new window can start this season.

Findings so far, walking forward through 2023-2025 (54 weeks) for each week's top 20:

| Ranking method | 2023-2025 | 2026 so far |
|---|---|---|
| Last 3 games average (baseline) | 0.162 | 0.186 |
| Season points per game | 0.205 | 0.188 |
| Current model | 0.241 | 0.268 |
| Current model + next game's context | 0.258 | 0.297 |

- A fixed 0.30 bar was miscalibrated: the model's 4-week average ranged from 0.05 to 0.37 and reached 0.30 in only 24% of windows, so passing would be largely luck. It beat the baseline's ranking in 80% of windows, and 87% with next-game context.
- Next-game context (home or away, dome, game total, implied team total) was the only input that helped in both periods, by about 0.02-0.03, which isn't conclusive on its own. It's now in the model.
- Season form and opponent defense added almost nothing, and gradient boosting did no better than Ridge.
- With next-game context, the replay of weeks 4-7 passes: ranking 0.24 vs a baseline of 0.15, MAE 6.92 vs 8.43. Live weeks are what count.

## When something fails

- **CI fails:** open the run from the commit's red X. For the backend, run `python -m pytest` from `backend/`. For the frontend, run `bunx tsc --noEmit` and `bun run build` from `frontend/`. Fix it on the branch and don't merge until it's green.
- **The daily job fails:** the site keeps its last good data, so nothing is urgent. Read the failed step in the Actions tab. Late or unavailable nflverse data usually clears by itself, so rerun it by hand or wait for the next day's run.
- **"No projectable players":** expected between seasons, when there are no upcoming games. Otherwise, check whether roster or schedule data changed.
- **The daily job stops running:** GitHub can pause scheduled workflows after 60 days without repo activity. Re-enable it from the Actions tab each September.
- **Bad data got published:** revert the job's commit. Don't edit the log by hand, because its git history is what proves predictions came before kickoff.

### Phase 6: Deployment preparation
- [ ] Decide whether to enforce CI. GitHub's required checks would also reject the daily job's direct commits to `main`, so it would need a bypass or a separate data branch
- [ ] Set the Vercel root directory to `frontend` and create a preview deploy
- [ ] Confirm the daily job's commit triggers a Vercel rebuild
- [ ] Test the preview on desktop and phone
- [ ] Add a short note to the site saying what the numbers are and when they were updated
- [ ] Remove the deprecated files flagged for manual removal

Done when: a preview URL shows current data without any manual steps.

### Phase 7: Public launch
- [ ] Promote to the production URL
- [ ] Share the link and confirm it works without cloning anything
- [ ] Watch the first week of unattended refreshes

Done when: anyone can open the link and see this week's projections.

### After launch
Roster-based pivots, more positions and the player news monitor, all described below.

## Deployment architecture

- **Frontend (React):** deploy to Vercel. Zero-config GitHub deploys, preview URLs per PR — a strong fit for a static/SSR React app.
- **No always-on backend:** a scheduled GitHub Action runs `train.py` and `evaluate.py`, then commits `frontend/public/data/projections.json` and the prediction log. That push rebuilds the site. It's free on a public repo, nothing sleeps, and git history proves when each prediction was made. Reasoning over a hosted API: projections are precomputed anyway, so a server would only add cold starts and another host to maintain. If a feature ever needs per-request logic, the deprecated Flask API in `backend/api/` is the starting point.

## Passing bar for the model

Scored in `backend/wr_predictor/predictions.py`, over the latest 4 finished weeks for the top 20 players as ranked before each game: all 20 predictions made, and better than the last-3-games baseline on both MAE and rank correlation. Prediction tracking takes priority over deploying.

Past-error features ("how far off was last week") are not in the model yet. Add them only if a backtest shows they beat the model without them, since one week's miss is often just touchdown luck.

## Deferred: rest-of-season (ROS) rankings

Not scheduled — needs a decision on approach before work starts. The current model only predicts one week ahead (`next_week_ppr_points`), so ROS isn't a free extension of it. Options, in increasing rigor:

1. **Chain the weekly model forward** — predict week N, feed that prediction into the rolling-average features, predict week N+1, repeat. Cheapest to build; error compounds each step out.
2. **New target variable** — e.g. `rest_of_season_avg_ppr`, trained directly rather than chained. More accurate, but is real modeling work: a new label in `targets.py` plus its own train/eval.
3. **Heuristic estimate** — project current usage metrics (target share, air yards) forward as a steady state, adjusted for schedule/byes. Fastest v1, least statistically rigorous.

Revisit once there's a clearer view on which trade-off is acceptable.

## Future feature: roster-based pivots

Rosters add a layer of organization beyond position rankings: when a top player is hurt, show who else on that team to pivot to. `filter_to_active_roster` already loads the weekly roster data this would build on. Not scheduled.

## Future feature: player news monitor

Not buildable yet — noted here so the design isn't lost before it's picked up.

**Goal:** when news breaks about a player (injury, role change, etc.), reflect its projected impact on that player's rankings — eventually automatically.

**Sketch:**
- **Ingestion:** a scheduled job polling news/injury sources (beat reporters, official injury reports, RSS/API feeds).
- **Impact scoring:** feed each item to an LLM with a structured prompt asking for a classification (severity, direction, confidence) rather than free text.
- **Applying it to projections — key design decision:** do *not* fold news sentiment into the trained model's features. The model's value is being a reproducible, leakage-free, stat-based forecast (see main [README.md](README.md)); mixing in sparse, hard-to-backtest LLM judgments would compromise that and make the model much harder to evaluate. Instead, apply news-driven adjustments as a **separate, clearly-labeled overlay** on top of the base projection (e.g. "base: 14.2 pts — flagged: questionable, hamstring, reported 9/2") rather than blending it into one number. Keeps the base model's integrity intact and the adjustment explainable.

This is its own project phase (ingestion + LLM classification + adjustment layer + UI surfacing), to be designed properly once the web app MVP and weekly rankings exist.
