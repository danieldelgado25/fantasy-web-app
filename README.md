# fantasy-web-app

A fantasy sports projection platform, built around statistics, probability, and machine learning rather than qualitative "expert rankings." The long-term goal is a web application that serves reproducible, pre-game fantasy projections across multiple sports.

This repository is the successor to [`wide-receiver-predictor`](https://github.com/danieldelgado25/wide-receiver-predictor), whose data pipeline and modeling code now live here as the project's foundation (`backend/wr_predictor/`). The repo is split into a `backend/` (pipeline + API) and a planned `frontend/` (React).

## Project Goal

Predict a wide receiver's fantasy football production (PPR points) for their next game, using only information that would have been available before that game was played — then, over time, expand the same discipline to more positions and more sports, and expose the results through a public web app.

Core commitments carried over from the original project:
- no data leakage — every feature must be knowable pre-game
- reproducible, code-based projections instead of qualitative rankings
- honesty about the limits of predicting a noisy, variance-driven sport

## Current Status

- **Data pipeline & model (NFL, WR):** functional. Pulls data via `nflreadpy`, filters to wide receivers, engineers pre-game features, builds a `next_week_ppr_points` target, and trains/evaluates models (baseline rolling average vs. Ridge regression).
- **Backend API:** skeleton only. A Flask app (`backend/api/`) exists with a health check route; the projections route is a stub — it isn't wired to the pipeline yet because there's no saved model artifact or single-row inference function to call.
- **Frontend:** not started. React was chosen as the framework; no code yet, and no npm packages have been installed.
- **Rest-of-season rankings, player news monitor:** deferred — see [ROADMAP.md](ROADMAP.md).
- **Other sports/positions:** not started. NFL WR remains the sole focus until the pipeline and app are proven out here.

## Data Pipeline

Main data source is `nflreadpy`. Fantasy-specific enrichment libraries from the ffverse ecosystem (`ffverse`, `ffopportunity`) may be incorporated later for opportunity-based metrics, but `nflreadpy` remains the primary workflow.

Dataset structure:
- one row per wide receiver per week
- only pre-game features
- target: next-week fantasy points

Feature categories in use or planned:
- previous week fantasy points
- rolling averages over recent games
- targets, receptions, air yards, and touchdowns
- target share and usage trends
- team offensive environment
- opponent defensive context
- game location and other situational factors

## Repository Structure

```
backend/
  wr_predictor/   # pipeline: data loading, filtering, features, targets, model training/eval
  api/             # Flask app — thin HTTP layer, imports wr_predictor, no modeling logic
  tests/           # unit tests for wr_predictor
  main.py          # builds datasets, runs baseline-vs-Ridge comparison
  requirements.txt
frontend/          # React app (planned, not yet scaffolded)
notebooks/          # experimentation only, not a home for reusable logic
```

`wr_predictor` and `api` are kept as separate packages under `backend/` on purpose: the pipeline has no concept of HTTP, and the API is a thin, replaceable adapter over it.

Run the pipeline/tests/API with `backend/` as the working directory (e.g. `cd backend && python main.py`, `cd backend && python -m pytest tests/`, `cd backend && python -m api.app`), after `pip install -r backend/requirements.txt`.

## Roadmap

1. Continue maturing the NFL WR pipeline and model.
2. Build the web app: React frontend (deployed to Vercel) + Flask backend/API (deployed separately — see [ROADMAP.md](ROADMAP.md) for why). Add model persistence and wire the `/api/projections` route to real inference.
3. Weekly rankings (sort projections — no new model required).
4. Extend modeling to additional NFL positions.
5. Extend to additional sports.
6. Open the app up for public use.

Deferred, not yet scheduled: rest-of-season rankings and a player news monitor — see [ROADMAP.md](ROADMAP.md).

## Disclaimer

This project is an analytics and learning tool, not a promise of accurate fantasy outcomes.
