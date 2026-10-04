# Roadmap — Restaurant Preparation Intelligence System

## Status

- **Phase 0 (Architecture) — this document set.** Reviewed 2026-09-08; architecture approved with 7 corrections, then a second pass added 4 more, then a third pass added 6 more for container-unit support, then a fourth pass added 5 more (22 total, see architecture.md §0). Awaiting final approval of the corrected documents before Phase 1 code begins.
- Phase 1 not yet started.

## Phase-by-Phase Plan (spec §32, unchanged ordering — restated with concrete exit criteria)

| Phase | Deliverable | Exit criteria |
|---|---|---|
| 0 | Architecture, schema, roadmap (this) | User approves this document set, corrected per architecture.md §0 |
| 1 | Core data | Catalog CRUD + seed data works end-to-end via API; `alembic upgrade head` runs clean on SQLite; `PreparationProductContainerSize` table and `PreparationProduct.preferred_prep_unit` column exist but are empty/unset (data-model.md §9); `StorageLocation.is_active` soft-delete behavior is tested alongside the other three catalog entities (architecture.md §0 correction 22) |
| 2 | Manual preparation stock | Stock-check screen (HTMX) lets a worker snapshot all active preparation products in under a minute; screen surfaces `stock_status`/staleness (data-model.md §5) so a worker can see which products have never been checked or are showing a stale reading |
| 3 | Demand input | Manual expected-order entry stored per `service_date` + `service_period`; `POST /demand/manual` body and `GET /demand` query both require `service_period` (preparation-engine.md §1, architecture.md §0 correction 21) |
| 4 | Preparation engine | `PreparationService.calculate(service_date, service_period)` passes all Phase-4 unit tests (preparation-engine.md §5, items 1–21), including the `LUNCH`/`DINNER` independence tests and the service-aware stock-check-window tests (item 17 — the exact morning-checked/dinner-`UNKNOWN`-until-re-check scenario, architecture.md §0 correction 19); `GET /inventory/preparation/current?service_date=&service_period=` agrees with what the calculation used (item 35); `convert_for_product` (§2.5) passes its unit tests, and `POST /inventory/preparation/snapshot`/`POST /menu-items/{id}/preparation-requirements` reject unverified container units at write time (item 36) |
| 5 | Priority engine | `PriorityService` passes items 22–32, including the simplified `shortage_score` formula across all five documented cases (items 24–28) and the `expected_usage_count`-based `demand_score` fix (item 32), using the 5-factor weighting (`w1..w5`, no `urgency_score` — architecture.md §0 correction 18); dashboard shows score + level + reasons |
| 6 | Kitchen dashboard | Full lifecycle (start/complete/override) usable on a tablet by a non-technical worker; quantities render in `preferred_prep_unit` (container size or measurable unit) where a verified conversion exists, degrading gracefully to the canonical unit otherwise (preparation-engine.md §2.5, item 37) |
| 7 | Raw ingredient layer | Recipes (`PreparationProduct` 1→many `PreparationRecipe`, one active) + `PreparationRecipeComponent` (raw ingredient **or** another preparation product, per data-model.md §6) + "can we prepare this?" recursive check against raw stock, with cycle detection in `RecipeService` |
| 8 | Historical order import | CSV import + weekday/hourly/dish statistics |
| 9 | Forecasting | Weekday average / moving average / weighted average, compared against actuals; introduces `PreparationBaseline` (weekday + service_period → typical quantity, often a container unit) per data-model.md §10 |
| 10 | Reservations | Manual + CSV reservation counts scale expected demand via historical dish distribution |
| 11 | Voice | STT → intent → Pydantic validation → existing service methods (DE + EN) |
| 12 | External integrations | E2N / POS / Resmio adapters behind existing provider interfaces |
| 13 | Optimization | Forecast improvement, waste reduction, safety-stock tuning using accumulated data |

## Phase 1 — Concrete Task Breakdown

1. `backend/` skeleton: `main.py`, `core/config.py`, `db/session.py`, `db/base.py`.
2. `core/units.py` (Decimal-based, see architecture.md §6) + `core/enums.py` (Unit — including `SMALL_BOX`/`MEDIUM_BOX`/`LARGE_BOX`/`XL_BOX`, data-model.md §9 — Dimension, PreparationStatus, PriorityLevel, DemandSource, `ServicePeriod`, `StockStatus`) with unit tests written first.
3. SQLAlchemy models: `StorageLocation` (including `is_active` — architecture.md §0 correction 22), `MenuItem`, `PreparationProduct` (including nullable `preferred_prep_unit`), `RawIngredient`, `MenuItemPreparationRequirement`, `PreparationProductContainerSize` (schema only, left empty — data-model.md §9). Quantity columns use `Numeric`, not `Float` (architecture.md §6).
4. Alembic: initial migration.
5. Pydantic schemas + repositories + thin routers for the 4 catalog entities (per API list in preparation-engine.md §1).
6. Seed data — **corrected sourcing** (data-model.md §7):
   - `data/seed_preparation_products.csv` — transcribed from the handwritten kitchen sheets (these sheets are Step-2 preparation products, spec §1/§33). Editable, **not** hardcoded into application logic.
   - `data/seed_menu_items.csv` — sourced from the restaurant's actual menu / manually verified menu data, **not** from the handwritten prep sheets.
   - `data/seed_raw_ingredients.csv` — starts **empty**, or with only explicitly verified raw ingredients. Do **not** infer raw ingredients from the handwritten preparation sheets; this file is expanded in Phase 7 once preparation recipes are documented.
   - `PreparationProductContainerSize` rows are **not** seeded at all in Phase 1, even from the handwritten sheets' box-count notes ("1 XL box") — those describe quantity to prepare, not a verified box weight. Conversions are entered one at a time, later, only once physically verified (data-model.md §9).
7. A seed script (`scripts/seed.py`) that loads the CSVs idempotently.
8. Basic tests: CRUD round-trip for each catalog entity, uniqueness constraint, soft-delete behavior — explicitly including `StorageLocation` (all four Phase 1 catalog entities now share the same `is_active` pattern, no exception).

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
- No per-product override of the stock-check windows or `MAX_STOCK_SNAPSHOT_AGE` — one global, per-`service_period` config for MVP (preparation-engine.md §2.4); a per-`PreparationProduct` override is a plausible later refinement once real usage shows some products need a tighter or looser window, not built now.
- No `urgency_score` in the MVP priority algorithm — removed (architecture.md §0 correction 18) for lack of a reliable input and a conflict with reproducibility; reintroduced only once real order-time-of-day data exists (Phase 8+).
- No priority-score adjustment for `stock_status = UNKNOWN` tasks — an unknown-stock task is surfaced with a warning but is not automatically boosted in `PriorityService`; left as a possible future refinement, not part of this correction.
- No universal/global box-size→weight table, ever — `PreparationProductContainerSize` conversions are always per-`PreparationProduct` (data-model.md §9); do not "simplify" this later by adding a shared default.
- No seeding of guessed `PreparationProductContainerSize` values in Phase 1 (or any phase) — every conversion is entered only once physically verified; the table starts empty.
- No `PreparationBaseline` computation or manual-entry UI before Phase 9 — the schema is documented (data-model.md §10) so it isn't a retrofit, but nothing reads or writes it before then.

## Definition of MVP Done (spec §39 — unchanged, restated as the north star)

A worker can, without editing source code: open the app → enter today's expected orders → enter current preparation stock → press calculate → see required preparation products, missing quantities, and priority order with an explanation → mark tasks in progress/completed → record final prepared quantity → repeat daily. This is the target at the end of **Phase 6**, not Phase 1.
