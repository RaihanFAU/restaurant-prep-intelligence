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

**Workflow 1 is complete and working end to end:**

```
PREPARE TOMORROW → ACTIVE TODAY/OVERDUE TASK LIST → COMPLETE TASK
```

Implemented: repositories, `PreparationTaskService`, Pydantic schemas, thin
FastAPI routes, a mobile-first Jinja2 + HTMX UI (home → station → product),
a no-auth worker-selection cookie, idempotent CSV-driven seed data, and 45
passing tests (model, service, and route/integration level).

**Not implemented yet** (by design, next step): product location tracking,
search. See `docs/mvp/kitchen-handover.md` §10.

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash; use .venv\Scripts\activate.bat for cmd.exe
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
python scripts/seed.py
```

`scripts/seed.py` is idempotent — safe to re-run any time. It loads
`data/{stations,sections,prepared_products}.csv` (demo data, not verified
restaurant truth — edit freely) and two demo workers, "Michael" and "Anna".

## Running the tests

```bash
python -m pytest tests/ -v
```

Current result: **45 passed** (14 model-layer, 17 `PreparationTaskService`
unit tests, 14 route/integration tests).

## Running the app

```bash
uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000/** in a browser (ideally your phone, on
the same network — this UI is mobile-first).

### Pages

| URL | What it is |
|---|---|
| `/` | Home — station cards with today's active-task counts |
| `/stations/{id}` | Station page — ÜBERFÄLLIG / HEUTE VORBEREITEN lists, then sections/products |
| `/products/{id}` | Product page — FÜR MORGEN VORBEREITEN button |
| `/worker/select?next=...` | Pick-your-name screen (no password, no real auth) |

### JSON API

| Method & path | Purpose |
|---|---|
| `POST /products/{product_id}/prepare-tomorrow?worker_id=` | Create tomorrow's task (or return "already marked") |
| `GET /stations/{station_id}/tasks/today` | Overdue + today's active tasks, sorted |
| `POST /tasks/{task_id}/complete?worker_id=` | Mark a task done |

The same two `POST` routes also serve HTML fragments instead of JSON when
called with an `HX-Request: true` header — that's what the UI's buttons use,
so tapping them updates the page without a full reload.

## Manual test checklist

**PASS → SALAT → Krautsalat → PREPARE TOMORROW → task list → DONE**

1. Open `/` — see 4 station cards (PASS, GRILL, FRITTEUSE, DESSERT), each
   showing "0 Artikel vorzubereiten" on a fresh seed.
2. You have no worker cookie yet — click "Wer bist du?" (or go straight to
   `/worker/select?next=/`). Pick "Michael" (or type a new name) and
   continue. You're redirected back to `/`.
3. Click the **PASS** card → `/stations/{id}`.
4. Under "BEREICHE" (sections), find **SALAT**, then click **Krautsalat** →
   `/products/{id}`.
5. Tap **FÜR MORGEN VORBEREITEN**. A green confirmation
   ("Für morgen vorgemerkt.") appears without the page reloading.
6. Tap it again — this time the message reads "Bereits für morgen
   vorgemerkt." and no second task was created (duplicate guard).
7. Go back to the **PASS** station page. Krautsalat does **not** appear
   yet — its task is due *tomorrow*, and the list intentionally only shows
   tasks due today or earlier.
8. To see the "today" and "overdue" states without waiting a day, use the
   API directly (or a Python shell) to backdate a task, e.g.:
   ```bash
   curl -X POST "http://127.0.0.1:8000/products/{another_product_id}/prepare-tomorrow?worker_id={worker_id}"
   ```
   then, in a Python shell (`python -c "..."` with `app.db.session.SessionLocal`),
   set that task's `due_date` to today (or yesterday) and commit.
9. Reload the **PASS** station page — the backdated product now appears
   under ÜBERFÄLLIG (if due_date was yesterday) or HEUTE VORBEREITEN (if
   today), with overdue items listed first.
10. Tap **FERTIG** on that task. It disappears from the active list
    immediately (HTMX swap, no full reload) and a "Erledigt." flash message
    appears.
11. Confirm it's still in the database as history (not deleted):
    ```bash
    curl http://127.0.0.1:8000/stations/{station_id}/tasks/today
    ```
    — the completed task is absent from this active list, but
    `PreparationTask.status = COMPLETED` rows are never deleted.

## Project layout

See `docs/mvp/kitchen-handover.md` §7 for the full rationale. Current state:

```
app/
├── main.py            # FastAPI app, routers, exception handlers, static mount
├── core/               # config, enums, i18n strings, worker-cookie dependency
├── db/                 # declarative Base, engine/session
├── models/             # SQLAlchemy ORM models (unchanged since step 1)
├── repositories/        # SQLAlchemy queries only — no business logic
├── services/            # PreparationTaskService — all business logic lives here
├── schemas/             # Pydantic request/response models
├── routes/              # thin FastAPI routers (pages, products, stations, tasks, worker)
├── templates/           # Jinja2 + HTMX, mobile-first
└── static/              # plain CSS + vendored htmx.min.js (no CDN dependency)
```

`schemas/`, `repositories/`, `services/`, `routes/` now have real content;
location tracking (the second MVP problem) is the next step, not yet built.

## Database

SQLite for development (`kitchen_handover.db`, git-ignored). Alembic manages
migrations; the first one (`alembic/versions/*_initial_schema.py`) creates
all seven tables: `stations`, `sections`, `storage_locations`, `workers`,
`prepared_products`, `preparation_tasks`, `product_location_history`.
(`storage_locations` and `product_location_history` exist in the schema
already but aren't used by any workflow yet.)

Notable constraints baked in at the database level (not just in Python):

- `preparation_tasks.status` has a `CHECK` constraint restricting it to
  `TO_PREPARE` / `COMPLETED`.
- A **partial unique index** on `preparation_tasks (prepared_product_id,
  due_date)` — scoped to `WHERE status = 'TO_PREPARE'` — prevents a
  duplicate active task for the same product and due date (pressing
  "prepare tomorrow" twice does not create two rows), while still allowing
  an unrelated overdue task and a new tomorrow-task to coexist. The service
  layer also catches the race-condition case (two near-simultaneous taps)
  and still returns a friendly "already marked" result instead of a 500.
- Foreign keys are enforced (tests turn on `PRAGMA foreign_keys=ON`
  explicitly, since SQLite doesn't do this by default).

## No authentication

There is no login. `/worker/select` sets a plain (unsigned) cookie
remembering which `Worker` row you are, purely so prepare-tomorrow/complete
actions can record who did them. Good enough for a shared kitchen tablet,
not meant to be secure.
