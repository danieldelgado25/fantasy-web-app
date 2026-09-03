**What is this project?**
- I want this project to be expanded into a projection model for more sports. 
- Right now, the focus is to be on NFL wide receivers.
- I also have future plans to potentially make this a web application.
- The intention is to learn more about ML models, gain experience with open source, and work with AI.
- This is a solo project

**What the project does (or at least should be doing)**
It's a data pipeline + modeling toolkit that predicts a wide receiver's fantasy football production (PPR points) for their next game, using only information that would have been available before that game was played.
*Pipeline:*
1. Pulls NFL data from nflreadpy
2. Filters to narrow on wide recievers
3. Takes raw stats and transforms them into inputs the model can learn from
4. Builds a supervised learning target "next_week_ppr_points"
5. Trains and evaluates models
6. Produces projections

**Who uses it?**
As of right now, only I am using this model. However I want to make the model available for public use. I am sure that it will take a lot of time and refinement, but this is a passion project I am willing to take that time with.

**What problem it solves?**
Fantasy football requires forecasting inherently noisy weekly player output. Existing "expert rankings" are often qualitative and non-reproducible. This project's problem statement is narrower and more rigorous: given only pre-game, publicly available usage and situational data, how accurately can a statistical/ML model predict a WR's next-week fantasy output — while being disciplined about not leaking future information into the prediction.

## Repo Structure

This repo is a fork of `wide-receiver-predictor` with a web layer added.

- `src/wr_predictor/` — the ML pipeline. Packaged via `pyproject.toml`; import
  it as `wr_predictor` (e.g. `from wr_predictor.dataset_builder import ...`).
  Install with `pip install -e .` (add `[webapp]` for the Flask deps).
- `tests/` — pipeline unit tests. Run `pytest` from the repo root.
- `notebooks/` — experimentation only.
- `backend/` — Flask API. Thin `routes.py` over three services
  (`wr_pipeline_service`, `model_service`, `projection_service`), plus
  `training/train_model.py` (offline trainer) and `artifacts/` (trained model).
  `backend/tests/` has its own suite.
- `frontend/` — React + Vite dashboard. Talks to the backend over HTTP only.

The web app must not reimplement pipeline logic — it imports `wr_predictor`
and consumes its output. Keep the pipeline unaware of Flask.

Open follow-up: `src/wr_predictor/model.py` and `backend/training/train_model.py`
are two different "first model" implementations that give different numbers.
Reconcile into one canonical implementation before relying on either.

## Behavior Guidelines
- Claude should limit assumptions to a maximum degree. 
- Every addition or removal should be accompanied by reasoning. 
- Always validate the integrity of the project after a removal or addition. 
- The only time that multiple files should be edited is in the context of minor tweaks being made to the multiple files. 
- Think in terms of intelligent commits. Keep the edits relevant to the task at hand. 
- If the task is too broad, ask me how it should be further divided up to best support clear organization. 
- I want summaries when tasks are completed. 
- I want descriptions for every variable, method, constructor, etc. 
- Add comments to all additions to best help readibility and organization of the files. 
- List all changes made when tasks are completed.
- Keep responses short. I do not need an affirmation machine. Get to the output.
- PRIORITIZE DESIGN ARCHITECTURE OVER FEATURES

## Hard Rules
- Claude should NOT be making 50+ line edits on multiple files at any point. 
- We would not be wanting to have 150+ lines edited in a single commit across the codebase.
- Don't install new npm packages without asking first. List what you'd install and why, then wait.
- Don't delete files. Mark them as deprecated with a comment instead, and flag them for manual removal.
