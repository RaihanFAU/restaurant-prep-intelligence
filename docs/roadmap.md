# Roadmap — Restaurant Preparation Intelligence System

## Status

- **Phase 0 (Architecture) — this document set.** Reviewed 2026-09-08; architecture approved with 7 corrections applied (see architecture.md §0). Awaiting final approval of the corrected documents before Phase 1 code begins.
- Phase 1 not yet started.

## Phase-by-Phase Plan (spec §32, unchanged ordering — restated with concrete exit criteria)

| Phase | Deliverable | Exit criteria |
|---|---|---|
| 0 | Architecture, schema, roadmap (this) | User approves this document set, corrected per architecture.md §0 |
| 1 | Core data | Catalog CRUD + seed data works end-to-end via API; `alembic upgrade head` runs clean on SQLite |
| 2 | Manual preparation stock | Stock-check screen (HTMX) lets a worker snapshot all active preparation products in under a minute |
| 3 | Demand input | Manual expected-order entry stored per `service_date` + `service_period` |
| 4 | Preparation engine | `PreparationService.calculate(service_date, service_period)` passes all Phase-4 unit tests (preparation-engine.md §5, items 1–18), including the `LUNCH`/`DINNER` independence tests and the `recorded_at`-cutoff current-stock tests |
| 5 | Priority engine | `PriorityService` passes items 19–24, including the safety-stock-only zero-division test (item 21); dashboard shows score + level + reasons |
| 6 | Kitchen dashboard | Full lifecycle (start/complete/override) usable on a tablet by a non-technical worker |
| 7 | Raw ingredient layer | Recipes (`PreparationProduct` 1→many `PreparationRecipe`, one active) + `PreparationRecipeComponent` (raw ingredient **or** another preparation product, per data-model.md §6) + "can we prepare this?" recursive check against raw stock, with cycle detection in `RecipeService` |
| 8 | Historical order import | CSV import + weekday/hourly/dish statistics |
| 9 | Forecasting | Weekday average / moving average / weighted average, compared against actuals |
| 10 | Reservations | Manual + CSV reservation counts scale expected demand via historical dish distribution |
| 11 | Voice | STT → intent → Pydantic validation → existing service methods (DE + EN) |
| 12 | External integrations | E2N / POS / Resmio adapters behind existing provider interfaces |
| 13 | Optimization | Forecast improvement, waste reduction, safety-stock tuning using accumulated data |

## Phase 1 — Concrete Task Breakdown

1. `backend/` skeleton: `main.py`, `core/config.py`, `db/session.py`, `db/base.py`.
2. `core/units.py` (Decimal-based, see architecture.md §6) + `core/enums.py` (Unit, Dimension, PreparationStatus, PriorityLevel, DemandSource, `ServicePeriod`) with unit tests written first.
3. SQLAlchemy models: `StorageLocation`, `MenuItem`, `PreparationProduct`, `RawIngredient`, `MenuItemPreparationRequirement`. Quantity columns use `Numeric`, not `Float` (architecture.md §6).
4. Alembic: initial migration.
5. Pydantic schemas + repositories + thin routers for the 4 catalog entities (per API list in preparation-engine.md §1).
6. Seed data — **corrected sourcing** (data-model.md §7):
   - `data/seed_preparation_products.csv` — transcribed from the handwritten kitchen sheets (these sheets are Step-2 preparation products, spec §1/§33). Editable, **not** hardcoded into application logic.
   - `data/seed_menu_items.csv` — sourced from the restaurant's actual menu / manually verified menu data, **not** from the handwritten prep sheets.
   - `data/seed_raw_ingredients.csv` — starts **empty**, or with only explicitly verified raw ingredients. Do **not** infer raw ingredients from the handwritten preparation sheets; this file is expanded in Phase 7 once preparation recipes are documented.
7. A seed script (`scripts/seed.py`) that loads the CSVs idempotently.
8. Basic tests: CRUD round-trip for each catalog entity, uniqueness constraint, soft-delete behavior.

Explicitly **out of scope for Phase 1**: any UI beyond what's needed to smoke-test the API (Swagger/OpenAPI docs are sufficient), demand entry, stock entry, and the calculation/priority engines — those are Phases 2–5.

## What Should NOT Be Built Yet (spec §1/§34, made explicit)

- No auth/RBAC system beyond a minimal `recorded_by`/`prepared_by` free-text or simple user reference.
- No React/Next.js frontend — HTMX/Jinja2/Tailwind is the MVP frontend choice (see architecture.md §5).
- No POS/E2N/Resmio integration code — interfaces only (`integrations/base.py`), no concrete adapters until Phase 12.
- No machine learning / forecasting model — not even a simple regression — until Phase 9, and even then starting with weekday/moving/weighted averages only (spec §15/§25).
- No voice/speech code — Phase 11.
- No multi-location / multi-tenant modeling.
- No pricing/cost tracking.
- No waste analytics UI — the `WasteRecord` table exists conceptually but isn't built until Phase 13.
- No microservices, message queues, or caching layer — single FastAPI process is sufficient at this scale.
- No automatic/AI-driven quantity changes anywhere — every quantity mutation is either a direct user action or a deterministic calculation a user triggers (spec §35).
- No `PreparationRecipeComponent` resolution logic (raw-ingredient-or-preparation-product recipe chaining, e.g. Sauce → Jus → raw ingredients) before Phase 7 — the schema is shaped to support it (data-model.md §6) but nothing reads it until then.

## Definition of MVP Done (spec §39 — unchanged, restated as the north star)

A worker can, without editing source code: open the app → enter today's expected orders → enter current preparation stock → press calculate → see required preparation products, missing quantities, and priority order with an explanation → mark tasks in progress/completed → record final prepared quantity → repeat daily. This is the target at the end of **Phase 6**, not Phase 1.
