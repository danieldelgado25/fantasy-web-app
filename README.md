# NFL Wide Receiver Fantasy Projections

A machine learning pipeline and website that project each NFL wide receiver's fantasy production for their next game, using only information available before kickoff. Predictions are saved publicly before each game and scored against what actually happened.

Fantasy football is noisy, so the goal isn't a perfect forecast. It's a reproducible model with an honest answer to one question: does it beat a simple alternative?

## Results so far

Replay of 2026 weeks 4-7, where each week's top 20 receivers were predicted using only earlier games:

| Measure | Model | Last-3-games average |
|---|---|---|
| Average points miss (MAE, lower is better) | 6.92 | 8.43 |
| Ranking of players (rank correlation, higher is better) | 0.24 | 0.15 |

These numbers are a test of the method, not proof. The real test is predictions saved before kickoff, starting with week 9 of 2026, in [`backend/predictions/`](backend/predictions/). A week's predictions freeze at kickoff, and the git history shows when each was made.

## How it works

```
nflverse data ──> features ──> one Ridge model per stat ──> projections.json ──> website
                                        │
                                        └──> prediction log ──> scored against actual results
```

A scheduled GitHub Action runs this daily during the season: it pulls fresh data, retrains, updates the projections and scores, and commits the results. That commit is what publishes new numbers to the site, so there's no backend server to host or keep awake.

- **Supervised learning:** Ridge regression, trained on past player-games labeled with what happened in the player's next game.
- **Projected stats:** targets, catches, receiving yards, receiving touchdowns, carries, rushing yards and official PPR points.
- **Inputs:** recent production and usage, target share, air yards, plus the next game's home or away status, dome, game total and implied team total.
- **Players:** the model trains on all receivers. The site highlights the top 20 by points so far, and search reaches the other active receivers.

## How it's evaluated

- **No future information:** every input must be known before kickoff. Past weeks are replayed by removing later games before any features are built, so a replay can't see the games it's predicting.
- **A simple baseline to beat:** each player's average over their last 3 games.
- **A passing bar:** over the latest 4 finished live weeks, all 20 predictions made, and better than the baseline on both MAE and ranking.
- **Weekly review:** predicted vs actual tables for targets, catches and points.

## What testing changed

Most ideas didn't survive testing, and the [project log on the site](frontend/src/lib/projectLog.ts) records them along with the ones that did. A few examples:

- **Removed weather:** game-time weather isn't known before kickoff. Accuracy didn't change, and usable training rows rose from 6,117 to 10,640.
- **Replaced my own target:** a fixed ranking score of 0.30 turned out to be largely luck over 4 weeks, because the score swung from 0.05 to 0.37. The bar now compares against the baseline.
- **Kept the simple model:** boosted trees, random forest, past prediction errors, 10 groups of extra opportunity data and touchdown-specific models didn't reliably beat Ridge regression.
- **Found the limit:** touchdowns drive the biggest misses and remain hard to predict, while target and catch totals stay close on average.

Full findings are in [ROADMAP.md](ROADMAP.md).

## Tech stack

| Area | Tools |
|---|---|
| Data | Python, Polars, [nflreadpy](https://github.com/nflverse/nflreadpy) |
| Modeling | scikit-learn |
| Website | React, TypeScript, TanStack Start, Tailwind CSS |
| Automation and hosting | GitHub Actions, Vercel |

The frontend was scaffolded with Lovable, and the project was developed with help from Claude Code. Learning to work well with AI tools is one of the project's goals.

## Repository layout

```
backend/
  wr_predictor/   pipeline: data loading, features, targets, models, prediction scoring
  train.py        trains the models and writes projections and the prediction log
  evaluate.py     scores predictions and writes accuracy results
  predictions/    prediction logs, review tables and reports
  tests/          unit tests
  api/            deprecated Flask API, replaced by the static projections file
frontend/         React site, reading its data from public/data/
notebooks/        data exploration
```

## Run it locally

```bash
# Backend, from backend/
pip install -r requirements-dev.txt
python -m pytest
python train.py
python evaluate.py          # add --replay to regenerate this season's past weeks

# Frontend, from frontend/
bun install
bun run dev
```

## Roadmap

The checklist and open decisions are in [ROADMAP.md](ROADMAP.md). Future ideas include roster-based pivots when a top player is hurt, rest-of-season rankings, a player news overlay and more positions.

## Disclaimer

This is an analytics and learning project. Projections are estimates, not guarantees or betting advice.
