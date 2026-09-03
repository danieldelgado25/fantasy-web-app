# fantasy-web-app

A fork of [`wide-receiver-predictor`](https://github.com/danieldelgado25/wide-receiver-predictor)
that keeps the original ML pipeline (`src/wr_predictor/`) and adds a web layer
around it: a Flask API (`backend/`) and a React dashboard (`frontend/`) that
serve the model's next-week PPR projections. The pipeline is now an installable
package, so the web app imports it directly instead of reaching across the
filesystem for a separate checkout.

Uses statistics, probability, and data analytics to forecast wide receiver fantasy football performance — or at least test how close we can get in a sport driven by chaos, variance, injuries, and small weekly sample sizes.

Predicting fantasy football output is difficult because weekly production is influenced by far more than raw talent alone. Matchups, target competition, quarterback play, injuries, touchdowns, game script, and randomness can all swing results from one week to the next.

This project does not aim to guarantee perfect predictions. The goal is to explore what can realistically be learned from historical NFL data, engineered features, and statistical modeling, with a specific focus on wide receivers. Since WR performance is heavily shaped by volume, efficiency, and situational context, it provides a strong use case for combining sports analytics with machine learning.

## Project Goal

Build a training-ready dataset and prediction pipeline that can estimate future fantasy performance for wide receivers based on past NFL usage and production trends.

The project is centered around:
- collecting historical weekly WR data
- engineering pregame features
- defining a fantasy-relevant target variable
- training and evaluating predictive models
- comparing results against the reality of football variance

## Data Direction

This project will use `nflreadpy` as the main Python data backbone.

Fantasy-specific enrichment libraries from the ffverse ecosystem may also be incorporated later where useful.

Possible future supplements include:
- `ffverse`
- `ffopportunity`

These may help add fantasy-relevant context such as opportunity-based metrics, but the main data workflow will be built around `nflreadpy`.

## Modeling Approach

The planned dataset structure is:

- one row per wide receiver per week
- only features that would be known before the predicted game
- a target such as next-week fantasy points

This setup is intended to avoid data leakage and create a cleaner foundation for machine learning.

Examples of future feature categories may include:
- previous week fantasy points
- rolling averages over recent games (noting greater volatility in certain players)
- targets, receptions, air yards, and touchdowns
- target share and usage trends
- team offensive environment
- opponent defensive context
- game location and other situational factors

## Development Structure

```
fantasy-web-app/
├── pyproject.toml        # packages the pipeline as `wr_predictor`
├── src/wr_predictor/     # the ML pipeline (data load, features, targets, model)
├── tests/                # pipeline unit tests
├── notebooks/            # experimentation, exploration, training, evaluation
├── backend/              # Flask API + service layer + offline trainer + artifact
└── frontend/             # React + Vite dashboard
```

Pipeline logic lives in reusable Python modules under `src/`. Jupyter notebooks
are reserved for experimentation, feature exploration, model training,
evaluation, and visualization — that separation keeps the project cleaner and
makes it easier to reuse code outside of notebooks. The web app never
reimplements pipeline logic; it imports `wr_predictor` and consumes its output.

## Web App

The pipeline is an installable package, so the web layer imports it with no
`sys.path` juggling and no separate checkout.

```bash
# From the repo root — installs the pipeline plus the Flask/serving deps.
pip install -e ".[webapp]"

# Backend API (http://localhost:5000)
cd backend
python run.py

# Frontend dashboard (http://localhost:5173), in another shell
cd frontend
npm install
npm run dev
```

The frontend talks to `http://localhost:5000` by default; override with
`VITE_API_BASE_URL`.

**Architecture.** `backend/` keeps a thin `routes.py` over three services:
`wr_pipeline_service` (the only caller of `build_training_dataset`, with an
in-memory cache), `model_service` (loads/serves the trained artifact), and
`projection_service` ("as of" row selection and filtering). Rationale is in
each module's docstring.

**Retraining.** `python backend/training/train_model.py` rebuilds the dataset
via the pipeline, trains Ridge with an alpha grid on a time-based split,
compares against a rolling-3-week-average baseline, and writes
`backend/artifacts/wr_model_v1.joblib` (+ `.metrics.json`). Re-run it when a new
week of NFL data lands or the pipeline's feature engineering changes.

**Known caveat.** Two "first model" implementations currently disagree
numerically: `src/wr_predictor/model.py` (drop-null rows, single Ridge fit) and
`backend/training/train_model.py` (median-impute, scale, alpha grid,
train/val/test). Reconciling them into one canonical implementation — and
regenerating the vendored artifact from it — is tracked as follow-up work.

## Why Wide Receivers?

Wide receivers are one of the most volatile fantasy positions, which makes them both frustrating and interesting to study. A receiver can post a huge week from a handful of targets or disappear despite strong usage. That makes WR prediction a good test bed for exploring:
- probability and uncertainty
- variance in sports performance
- feature engineering
- model limitations in noisy real-world data

## Disclaimer

This project is an analytics and learning tool, not a promise of accurate fantasy outcomes.