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

No quantities, forecasting, AI, recipes, or integrations.

## Current status

**Workflow 1, real authentication (with a fast PIN login for daily
worker use), role-based admin, and manual task priority are complete and
working end to end:**

```
Login → Product → PREPARE TOMORROW → Today/Overdue task list → Complete
```

- Two separate login flows:
  - **`/login`** — email + password (Argon2-hashed). For `ADMIN` accounts.
  - **`/worker-login`** — worker name + 4-digit PIN (also Argon2-hashed).
    For everyday `WORKER` use — much faster to type on a shared kitchen
    device than an email and password every shift. A PIN can never grant
    `ADMIN` access, and repeated wrong PINs temporarily lock the account
    (see "Worker PIN login" below).
  - Both **replace** the original "pick any worker's name" mechanism,
    which let one worker complete tasks under another worker's name. The
    acting worker is always the authenticated session user; the server
    never trusts a client-supplied worker id.
- Two roles: `ADMIN`, `WORKER`. Admin routes are protected server-side
  (a `WORKER` hitting `/admin` gets `403`, not just a hidden button).
- `/admin` dashboard: manage prepared products, stations, sections, user
  accounts (incl. worker PINs), and task priority/pinning — no more
  editing CSVs or Python to add a product.
- Simple manual priority (`NORMAL`/`HIGH`/`URGENT`) + an orthogonal "pin to
  top" flag, with a documented sort order.
- CSRF protection (double-submit cookie) on every state-changing request.

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
python scripts/create_admin.py
```

`scripts/seed.py` is idempotent — safe to re-run any time. It loads
`data/{stations,sections,prepared_products}.csv` (demo catalog data, not
verified restaurant truth — edit freely). It no longer seeds demo worker
accounts — see "Creating accounts" below.

### Production configuration

Three environment variables matter outside of local dev — set them in `.env`
(or real environment variables in production), not in source code:

| Variable | Default | Production value |
|---|---|---|
| `SESSION_SECRET_KEY` | an insecure, obviously-fake dev default | a long random value: `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `COOKIE_SECURE` | `false` | `true` **once served over HTTPS** — leave `false` for local/LAN HTTP testing, or login cookies silently won't be set |
| `OPERATIONAL_DAY_CUTOFF` | `04:00` | confirm with the actual kitchen — see "Operational (business) day" below |

## Creating accounts (no public registration)

**First admin** — run once, interactively (password is not echoed, never
put a real password on the command line or in Git):

```bash
python scripts/create_admin.py
```

Refuses to run again once an admin already exists (pass `--force` to
override, e.g. resetting a dev DB).

**Worker accounts** — log in as an admin and use `/admin/users`: display
name, email, a 4-digit PIN (entered twice), role (defaults to `WORKER`).
This is the normal day-to-day case — workers log in at `/worker-login`
with their name and that PIN, not email+password.

**Additional admin accounts** — there's no UI form for this (an `ADMIN`
account always needs a password, and the `/admin/users` form only ever
collects a PIN). Either run `python scripts/create_admin.py --force`
again, or promote an existing worker: use `/admin/users/{id}/edit` to set
a password for them first (the password-reset form works on any
account), then change their role to `ADMIN`. Trying to promote someone
with no password set is rejected with a clear error telling you to set
one first.

From `/admin/users/{id}/edit` an admin can also change a worker's role,
activate/deactivate them, reset their password, or reset their PIN (which
also clears any active lockout — see below). The system always keeps at
least one active admin — you cannot deactivate or demote the only
remaining one.

### Worker PIN login

- A PIN is exactly 4 numeric digits, Argon2-hashed exactly like a
  password — never stored or logged in plain text.
- After **5** wrong PINs in a row for the same worker, further attempts
  (even the correct PIN) are refused for **15 minutes**
  (`pin_max_failed_attempts` / `pin_lockout_seconds` in `app/core/config.py`).
  A correct login, or an admin resetting the PIN, clears the count.
- The login error is identical whether the worker name doesn't exist, the
  account has no PIN, it belongs to an `ADMIN`, or the PIN is simply
  wrong — never reveals which.

## Roles

| | WORKER | ADMIN |
|---|---|---|
| Browse stations/products, prepare tomorrow, view today/overdue tasks, complete tasks | ✅ | ✅ |
| `/admin` (products, stations, sections, users, tasks) | ❌ (403) | ✅ |

## Running the tests

```bash
python -m pytest tests/ -v
```

Current result: **87 passed** — model layer, `PreparationTaskService`,
route/integration, authentication & identity/audit, admin catalog
management, admin user management, priority/pinning, and worker PIN
login (creation, hashing, login, lockout, admin PIN reset).

## Running the app

```bash
uvicorn app.main:app --reload
```

- App: **http://127.0.0.1:8000/** (redirects to `/login` until you sign in)
- Admin dashboard: **http://127.0.0.1:8000/admin** (ADMIN role only)

### Pages

| URL | What it is |
|---|---|
| `/login` | Admin login — email + password |
| `/worker-login` | Worker login — name + 4-digit PIN (the everyday entry point) |
| `/` | Home — station cards with today's active-task counts |
| `/stations/{id}` | Station page — pinned/ÜBERFÄLLIG/HEUTE VORBEREITEN lists, then sections/products |
| `/products/{id}` | Product page — FÜR MORGEN VORBEREITEN button |
| `/admin` | Admin dashboard |
| `/admin/products`, `/admin/stations`, `/admin/sections`, `/admin/users`, `/admin/tasks` | Admin CRUD pages |

### JSON API

| Method & path | Purpose |
|---|---|
| `POST /products/{product_id}/prepare-tomorrow` | Create tomorrow's task as the logged-in user (or return "already marked") |
| `GET /stations/{station_id}/tasks/today` | Pinned/overdue/today's active tasks, sorted |
| `POST /tasks/{task_id}/complete` | Mark a task done as the logged-in user |

All three require a valid session cookie; the two `POST`s also require the
CSRF token (`X-CSRF-Token` header, matching the `csrf_token` cookie). They
serve HTML fragments instead of JSON when called with `HX-Request: true` —
that's what the UI's buttons use, so tapping them updates the page without
a full reload.

## Task priority & pinning

Every `PreparationTask` has `priority` (`NORMAL`/`HIGH`/`URGENT`, default
`URGENT` — a product only gets "prepare tomorrow"'d because someone noticed
it's finished, which is inherently urgent) and an independent `is_pinned`
flag. An admin can change either from `/admin/tasks`.

Station task lists sort: **pinned first, then overdue before today's, then
URGENT > HIGH > NORMAL, then alphabetically** as a final tiebreaker. Pinning
always wins — a pinned `NORMAL` task outranks an unpinned `URGENT` one.

## Operational (business) day

The kitchen's working day doesn't reset at literal calendar midnight. A
worker going home at 00:30 and remembering "Krautsalat needs to be ready
for the morning" means the morning that's about to start, not the one
after it — even though the calendar has already rolled over to a new
date.

To handle this, every scheduling decision (`PREPARE TOMORROW`,
today/overdue, the tomorrow queue, home counters) resolves "today"
through `get_operational_date()` in `app/core/operational_day.py`
instead of literal calendar `date.today()`:

- Before a configurable cutoff (**`OPERATIONAL_DAY_CUTOFF`, dev default
  `04:00` Europe/Berlin — a placeholder, not confirmed restaurant
  truth**), the operational date is still *yesterday's* calendar date.
- `PREPARE TOMORROW` always targets `operational_date + 1`.

Example: pressing `PREPARE TOMORROW` at **00:30** (cutoff `04:00`) still
resolves to the previous operational day, so the task is due the very
next morning — not the morning after. Pressing it at **23:30** the
evening before works the same way it always did.

**Early completion:** any active task — including one still sitting in
the tomorrow queue — can be marked `FERTIG` the moment it's actually
finished, regardless of its due date. `due_date` is never changed by
completing early; only `completed_at`/`completed_by` are set, so the
original due date stays intact for history. A task completed this way
disappears from the tomorrow queue (and the home counter) immediately,
and never reappears when its due date naturally arrives — it's the same
database row, already `COMPLETED`.

## Manual test checklist

A-T below mirrors a real shift handover: an admin sets up two worker
accounts, one worker starts something, another finishes it, and the admin
reviews/reprioritizes afterward.

**A. Create the first admin**
```bash
python scripts/create_admin.py
```

**B. Login as admin** — open `/login`, sign in.

**C-D. Create two worker accounts** — `/admin/users`: create "Raihan"
(PIN `1234`, role `WORKER`) and "Ana" (PIN `5678`, role `WORKER`).

**E. Logout** — the header's `ABMELDEN` link.

**F. Login as Raihan** — at `/worker-login` this time, not `/login`: pick
"Raihan" from the dropdown, enter PIN `1234`.

**G. Mark Krautsalat "prepare tomorrow"** — PASS → SALAT → Krautsalat →
`FÜR MORGEN VORBEREITEN`.

**H. Verify the task records Raihan** — check `/admin/tasks`: "Erstellt
von" (created by) shows Raihan, not anyone else.

**I. Logout. J. Login as Ana** — `/worker-login`, PIN `5678`.

**K. Verify Ana cannot act as Raihan** — there is no worker-selection UI
anymore, and Ana doesn't know Raihan's PIN; the acting identity is always
whoever is logged in. (If you want to prove this at the HTTP level:
`curl`'ing `/tasks/{id}/complete?worker_id=<raihan's id>` while logged in
as Ana still records Ana — the query param is simply never read.)

**L. Complete a different task as Ana** (any active task — back-date one to
today first if everything is still due tomorrow; see note below).

**M. Verify the completion records Ana** — `/admin/tasks` → "Erledigt von"
(completed by) shows Ana.

**N. Login as admin again. O. Open `/admin`.**

**P. Add a prepared product** — `/admin/products` → fill the form → add.

**Q. Edit it** — `/admin/products/{id}/edit`, change the name, save.

**R. Set a task's priority** — `/admin/tasks`, change a task's priority
dropdown (auto-submits).

**S. Pin a lower-priority task** — e.g. a `HIGH` task — via the `ANHEFTEN`
button.

**T. Verify it now sorts first** — reload `/stations/{id}` or
`GET /stations/{id}/tasks/today`: the pinned task is first, even ahead of
`URGENT` ones.

**U. Trigger the PIN lockout** — at `/worker-login`, enter the wrong PIN
for Raihan 5 times in a row; the 6th attempt (even with the correct PIN)
is refused for 15 minutes.

**V. Admin resets the PIN** — as admin, `/admin/users/{raihan's id}/edit`
→ enter a new PIN twice → `PIN ZURÜCKSETZEN`. This also clears the
lockout from step U, so Raihan can log in immediately with the new PIN.

> **Note on "today" during manual testing:** a freshly created task from
> `PREPARE TOMORROW` is due *tomorrow* by design, so it won't show in
> today's list yet. To see it immediately for testing, either use
> `/admin/tasks` → create a manual task with today's date, or open a Python
> shell (`SessionLocal` from `app.db.session`) and set an existing task's
> `due_date` back to today.

## Project layout

```
app/
├── main.py             # FastAPI app, middleware, routers, exception handlers
├── core/                # config, enums, i18n, security (Argon2), session
│                         # tokens, CSRF middleware, auth dependencies
├── db/                  # declarative Base, engine/session
├── models/              # SQLAlchemy ORM models
├── repositories/         # SQLAlchemy queries only — no business logic
├── services/             # PreparationTaskService, auth_service,
│                          # catalog_admin_service, user_admin_service
├── schemas/              # Pydantic request/response models
├── routes/               # thin FastAPI routers (auth, pages, products,
│                          # stations, tasks, admin*)
├── templates/            # Jinja2 + HTMX, mobile-first; templates/admin/
│                          # for the back office
└── static/               # plain CSS + vendored htmx.min.js (no CDN dependency)
```

## Database

SQLite for development (`kitchen_handover.db`, git-ignored). Alembic
manages migrations — three so far: the initial schema, then
`add_auth_fields_to_worker_and_priority_to_preparation_task` (added
`email`/`password_hash`/`role`/`created_at`/`updated_at` to `workers` and
`priority`/`is_pinned` to `preparation_tasks`), then
`add_worker_pin_authentication` (added `pin_hash`/`failed_pin_attempts`/
`pin_locked_until` to `workers`, and loosened `password_hash` from
`NOT NULL` to nullable — a PIN-only `WORKER` account never gets one).

**One unavoidable dev-data change, documented in that migration's
docstring:** it deletes the old "Michael"/"Anna" demo `Worker` rows. They
had no email/password and *were* the free worker-selection mechanism this
change removes — they cannot be grandfathered into the new schema. The
delete fails loudly (a foreign-key error) rather than silently orphaning
anything if a `PreparationTask` ever referenced them; in this project's dev
database none did.

Notable constraints at the database level (not just in Python):

- `workers.email` is unique; `workers.role` and `preparation_tasks.status`/
  `priority` all have `CHECK` constraints restricting them to their valid
  enum values.
- A **partial unique index** on `preparation_tasks (prepared_product_id,
  due_date)` — scoped to `WHERE status = 'TO_PREPARE'` — prevents a
  duplicate active task for the same product and due date, while still
  allowing an unrelated overdue task and a new tomorrow-task to coexist.
- Foreign keys are enforced (tests turn on `PRAGMA foreign_keys=ON`
  explicitly, since SQLite doesn't do this by default).

## Security notes

- Passwords and PINs: both Argon2 (`argon2-cffi`), never logged, never
  stored in plaintext. A PIN is treated as "just a short password" —
  same hashing call, no separate scheme.
- Sessions: a signed, timestamped cookie (`itsdangerous`) — not a JWT, no
  server-side session table. `HttpOnly`, `SameSite=Lax`, `Secure` in
  production (see `COOKIE_SECURE` above). 14-day expiry by default.
- CSRF: double-submit cookie on every state-changing request.
- Login responses don't distinguish "unknown email" from "wrong password"
  (or, on the PIN side, "unknown worker" from "wrong PIN" from "that's an
  ADMIN account"), and check against a dummy hash when the account doesn't
  exist, to avoid leaking account existence through response content or
  timing.
- PIN login has basic brute-force protection: 5 wrong PINs in a row locks
  that account out for 15 minutes (see "Worker PIN login" above) — a
  password login has no equivalent lockout, since a password is assumed
  to have enough entropy that this MVP doesn't need one.
- Nothing here is enterprise-grade (no 2FA, no audit log beyond what
  `created_by`/`completed_by`/`role` already capture) — appropriate for a
  single-restaurant kitchen tool, not a public-facing system.
