# Kitchen Prep Handover & Location Tracker (MVP)

A small, standalone MVP — **not** the long-term Restaurant Preparation
Intelligence System documented at the repo root (`docs/architecture.md` etc.,
unchanged by this project). Full spec: [`docs/mvp/kitchen-handover.md`](../docs/mvp/kitchen-handover.md).

It solves exactly two problems for a real kitchen:

1. **Bad handover** — a worker marks a prepared product "prepare tomorrow"
   in a few taps, so the next day's worker sees it instead of discovering a
   shortage mid-service.
2. **Lost products** — a worker records where a prepared product currently
   is, so the next worker can search for it instead of checking every
   fridge/Kühlhaus.

No quantities, forecasting, AI, recipes, or integrations — see the spec's
"non-goals" section.

## Current status

Step 1 of the implementation order is done: **project skeleton + database
models + migration + model tests.** No routes/UI/business-logic services
exist yet — see `docs/mvp/kitchen-handover.md` §10 for what's next.

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash; use .venv\Scripts\activate.bat for cmd.exe
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
```

## Running the tests

```bash
python -m pytest tests/ -v
```

## Running the (placeholder) app

```bash
uvicorn app.main:app --reload
```

Only `GET /health` exists so far.

## Project layout

See `docs/mvp/kitchen-handover.md` §7 for the full folder structure and
rationale. In short: `app/models` is the only layer with real content right
now; `schemas/`, `repositories/`, `services/`, `routes/`, `templates/`,
`static/` are empty packages waiting for the next steps.

## Database

SQLite for development (`kitchen_handover.db`, git-ignored). Alembic manages
migrations; the first one (`alembic/versions/*_initial_schema.py`) creates
all seven tables: `stations`, `sections`, `storage_locations`, `workers`,
`prepared_products`, `preparation_tasks`, `product_location_history`.

Notable constraints baked in at the database level (not just in Python):

- `preparation_tasks.status` has a `CHECK` constraint restricting it to
  `TO_PREPARE` / `COMPLETED`.
- A **partial unique index** on `preparation_tasks (prepared_product_id,
  due_date)` — scoped to `WHERE status = 'TO_PREPARE'` — prevents a
  duplicate active task for the same product and due date (pressing
  "prepare tomorrow" twice does not create two rows), while still allowing
  an unrelated overdue task and a new tomorrow-task to coexist.
- Foreign keys are enforced (tests turn on `PRAGMA foreign_keys=ON`
  explicitly, since SQLite doesn't do this by default).
