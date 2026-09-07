# Preparation Engine — API, Calculation Service, Priority Algorithm, Test Cases

Phase 0 deliverable. This is the core of the product (spec §5) — everything else is scaffolding around this.

## 1. First API Endpoints (Phase 1 scope, others noted)

Routes are thin: parse/validate request → call one service method → map response. No business logic here.

```text
# Phase 1 — catalog CRUD
GET    /menu-items
POST   /menu-items
GET    /menu-items/{id}
PATCH  /menu-items/{id}            # includes soft-delete via is_active=false

GET    /preparation-products
POST   /preparation-products
GET    /preparation-products/{id}
PATCH  /preparation-products/{id}

GET    /raw-ingredients
POST   /raw-ingredients

GET    /storage-locations
POST   /storage-locations

GET    /menu-items/{id}/preparation-requirements
POST   /menu-items/{id}/preparation-requirements
DELETE /menu-item-preparation-requirements/{id}

# Phase 2 — preparation stock
POST   /inventory/preparation/snapshot        # one or more {preparation_product_id, quantity, unit}
GET    /inventory/preparation/current         # latest snapshot per product

# Phase 3 — demand
POST   /demand/manual                         # {service_date, menu_item_id, expected_quantity}
GET    /demand?service_date=

# Phase 4 — calculation
POST   /preparation/calculate?service_date=&service_period=   # runs PreparationService, (re)creates PreparationTask rows for that (date, period)
GET    /preparation/today?service_period=     # today's tasks for the given period, ranked (Phase 5 adds priority fields)
                                               # service_period is required; the UI defaults it to the next
                                               # upcoming service (LUNCH before ~14:00 local, else DINNER),
                                               # but the API itself does not guess

# Phase 6 — task lifecycle
POST   /preparation/tasks/{id}/start
POST   /preparation/tasks/{id}/complete       # body: {final_quantity, prepared_by}
POST   /preparation/tasks/{id}/override       # body: {final_quantity, override_reason, overridden_by}

# Later phases (not built yet)
GET    /analytics/waste                       # Phase 13
GET    /analytics/forecast-accuracy           # Phase 9
POST   /voice/command                         # Phase 11
```

Deliberately **not** building yet: bulk import endpoints, auth endpoints, analytics endpoints, voice endpoints, reservation endpoints. These are placeholders in the roadmap only.

## 2. Preparation Calculation Service

### 2.1 Responsibility

`PreparationService.calculate(service_date, service_period)` is the single deterministic function that turns (expected demand + recipe mapping + current stock + safety stock) into `PreparationTask` rows, scoped to one service period. It must be pure with respect to its inputs — same inputs, same output, every time (spec §10, §29). `service_period` is required, not optional (data-model.md §4) — there is no "calculate for the whole day" mode, because lunch and dinner shortages are independent.

### 2.2 Algorithm

```text
function calculate_preparation(service_date, service_period):
    demand = get_all_demand_forecasts(service_date, service_period)   # [ (menu_item_id, expected_quantity) ]
    requirements = get_all_menu_item_requirements()                    # [ (menu_item_id, prep_product_id, qty_per_portion, unit) ]

    # Step 1 — explode menu demand into per-product required quantity
    required_by_product = {}   # prep_product_id -> normalized Decimal quantity (canonical unit)
    for (menu_item_id, expected_qty) in demand:
        for req in requirements where req.menu_item_id == menu_item_id:
            normalized_qty = convert(req.quantity_per_portion, req.unit, canonical_unit(req.preparation_product_id))
            required_by_product[req.preparation_product_id] += expected_qty * normalized_qty

    # Step 2 — for every preparation product with a requirement OR existing stock record
    for product in preparation_products where product.id in required_by_product or has_stock_record(product.id):
        required = required_by_product.get(product.id, 0)
        available = get_current_stock(product.id, service_date, service_period)   # see §2.4 — latest snapshot as-of cutoff, normalized
        safety = normalize(product.safety_stock)

        prepare_quantity = required + safety - available

        if prepare_quantity <= 0:
            skip (no task created) — optionally log "no preparation required"
        else:
            upsert PreparationTask(
                preparation_product_id = product.id,
                service_date = service_date,
                service_period = service_period,
                required_quantity = required,
                available_quantity = available,
                safety_quantity = safety,
                prepare_quantity = prepare_quantity,
                unit = product.default_unit,
                status = NOT_STARTED,
            )   # upsert key: (preparation_product_id, service_date, service_period) — data-model.md §4

    return all tasks for (service_date, service_period), handed to PriorityService for scoring
```

All arithmetic above (`required`, `available`, `safety`, `prepare_quantity`) is `Decimal`, matching the `NUMERIC` columns — see architecture.md §6.

### 2.4 Current Stock Selection — `get_current_stock(product_id, service_date, service_period)`

Full semantics (summary in data-model.md §5): "current stock" is **not** the latest `PreparationStock` row for the calendar day. It is the latest row by `recorded_at` at or before that service period's **planning cutoff**:

```text
get_current_stock(product_id, service_date, service_period):
    cutoff = planning_cutoff(service_date, service_period)
        # e.g. LUNCH  -> service_date at the configured lunch-prep start time
        #      DINNER -> service_date at the configured dinner-prep start time
        # (configurable per restaurant; not hardcoded — a kitchen's lunch/dinner
        #  prep start times are operational config, not a constant)

    candidate = the PreparationStock row for product_id with the greatest
                recorded_at such that recorded_at <= cutoff

    if candidate exists:
        return candidate.quantity (normalized to canonical unit)
    else:
        # no snapshot at all before this cutoff (e.g. first day of use, or a
        # product nobody has checked yet) — treat as zero, not an error, and
        # surface a "never checked" warning alongside the resulting task
        return 0, with a data-quality warning attached
```

This is exactly what makes the intended intra-day flow work without special-casing it:

```text
morning snapshot (07:00)  --------------------------------> covers LUNCH cutoff (11:30)
        lunch service consumes stock (not recorded automatically — MVP has no auto-decrement)
afternoon re-check snapshot (16:00) ------------------------> covers DINNER cutoff (17:30), supersedes the morning snapshot
```

`DINNER` planning naturally picks up the 16:00 re-check because it is the latest row `<= 17:30`; `LUNCH` planning on the same day is unaffected because 16:00 is after its own 11:30 cutoff. No stock row is ever "for lunch" or "for dinner" — the row is just a timestamped fact, and each planning run picks the right one as-of its own cutoff. This also means recording a stock snapshot *during* dinner service does not retroactively corrupt the dinner plan that already used the 16:00 snapshot, because that calculation already ran and its `PreparationTask` row is not silently recalculated (§2.3 recalculation rule).

### 2.3 Edge cases (explicit, not accidental)

- **Menu item with no preparation mapping** → contributes 0 to every product; does not error; flagged in a warnings list returned alongside tasks (visible to chef, not hidden).
- **Preparation product with no recipe** → irrelevant to this calculation (recipes are Phase 7 / raw ingredient layer); shortage calc doesn't require a recipe to exist.
- **No expected demand entered for the day** → `required_by_product` is empty; the calculation still runs and creates tasks *only* for products with negative safety-vs-stock coverage (i.e., simply low on standing safety stock), so the system still surfaces "you're below safety stock" even before anyone enters covers.
- **Same preparation product used by multiple menu items** → summed in Step 1 by construction (spec §10, §28's Dish A example).
- **Duplicate `MenuItemPreparationRequirement` rows** (same menu_item + same product) → summed rather than rejected at calc time, but flagged as a data-quality warning; uniqueness should also be enforced at write time in `POST /menu-items/{id}/preparation-requirements` to prevent accidental duplicates in the first place.
- **Incompatible units** (e.g., recipe says `piece`, but product's canonical unit is `kg`) → `convert()` raises `IncompatibleUnitError`; the calculation fails loudly for that one line item (surfaced as a data error to fix in the catalog), it does not silently guess or drop the term.
- **Recalculation** (`POST /preparation/calculate` called twice for the same `(date, service_period)`) → upsert semantics on `(preparation_product_id, service_date, service_period)`; a task already `IN_PROGRESS`/`COMPLETED` is **not** silently overwritten — recalculation only touches `NOT_STARTED` tasks and reports a diff for the rest ("required quantity changed from 10kg to 12kg for Bratkartoffeln, already in progress — review manually").
- **Same product, different service periods on the same day** → `LUNCH` and `DINNER` tasks for the same `preparation_product_id`/`service_date` are independent rows (different `service_period`), each with its own `get_current_stock` cutoff (§2.4); they are never merged or compared to each other by the calculation.

## 3. Priority Algorithm (explainable, spec §11)

### 3.1 Principle

No opaque AI score. Every factor is a named, independently-computed sub-score in `[0, 1]`, combined with configurable weights, and every task carries the human-readable reasons that produced its score.

### 3.2 Sub-scores

```text
shortage_score:
    if required_quantity > 0:
        shortage_score = clamp(prepare_quantity / required_quantity, 0, 1)
        # 1.0 = we have nothing of what's required; 0 = fully covered
    elif safety_quantity > 0:
        # safety-stock-only task: no menu demand at all (required_quantity == 0),
        # but current stock has fallen below the standing safety stock.
        # required_quantity is not a meaningful denominator here (division by
        # zero) — safety_quantity is the correct "what shortfall are we
        # measuring against" denominator instead.
        shortage_score = clamp(prepare_quantity / safety_quantity, 0, 1)
    else:
        # required_quantity == 0 and safety_quantity == 0: prepare_quantity
        # cannot be positive here (prepare_quantity = required + safety -
        # available, and available >= 0), so a task would not have been
        # created for this product at all. Defined for completeness only.
        shortage_score = 0

demand_score           = normalize(required_quantity against today's distribution of required_quantity
                                     across all tasks — e.g. percentile rank)

dependency_score       = normalize(count of distinct menu items requiring this product
                                     against max dependency count today)

prep_time_score        = normalize(prep_time_minutes against max prep_time_minutes today)
                         # longer prep → start sooner → higher score

urgency_score          = based on earliest_expected_need vs. now
                         # e.g. hours_until_service is small → score closer to 1

emergency_difficulty_score = product.difficulty_score (0-1, pre-configured per product;
                         "how bad is it to make this last-minute / mid-service")

priority_score = shortage_score   * w1
               + demand_score     * w2
               + dependency_score * w3
               + prep_time_score  * w4
               + urgency_score    * w5
               + emergency_difficulty_score * w6

# w1..w6 configurable, default (sum = 1.0):
w1=0.35 (shortage)  w2=0.15 (demand)  w3=0.15 (dependency)
w4=0.15 (prep_time) w5=0.10 (urgency) w6=0.10 (emergency difficulty)
```

### 3.3 Priority levels (thresholds configurable)

```text
priority_score >= 0.75  → CRITICAL
priority_score >= 0.50  → HIGH
priority_score >= 0.25  → NORMAL
priority_score <  0.25  → LOW
prepare_quantity <= 0   → READY (not scored / excluded from the actionable list)
```

### 3.4 Explanation generation

Each sub-score above a small threshold contributes one human-readable reason line, ordered by contribution magnitude (`sub_score * weight`, descending). Example (matches spec §11):

```text
Jus — CRITICAL (score 0.81)

Reasons:
- only 25% of required stock is available     (shortage_score contribution)
- used by 4 menu items                        (dependency_score contribution)
- expected demand is high                     (demand_score contribution)
- preparation takes 45 minutes                (prep_time_score contribution)
```

`reason_text` on `PreparationTask` stores this generated explanation (plain text, regenerated on every calculation — never hand-edited, since it must always match the score that produced it).

### 3.5 Explicitly not doing (per spec §35)

- No ML-based/learned scoring for MVP. Weights are static config, tuned by a human, not fit from data, until Phase 13 at the earliest.
- No LLM in the scoring path. LLMs are only usable later for voice intent parsing (Phase 11) and natural-language summaries of an already-computed dashboard — never to produce the score itself.

## 4. Worked Example (validates the design against spec §6/§28)

```text
Dish A requires 200 g Bratkartoffeln per portion.
Expected orders: 10  →  required = 2.0 kg
Current stock:   0.5 kg
Safety stock:    0.2 kg

prepare_quantity = 2.0 + 0.2 - 0.5 = 1.7 kg   ✓ matches spec §28 expected result
```

## 5. Test Cases (spec §28, expanded)

Unit tests for `core/units.py`:
- kg↔g and L↔ml round-trip conversion, using `Decimal` inputs/outputs (not `float`) — see architecture.md §6
- converting between incompatible dimensions raises `IncompatibleUnitError` (kg→L, piece→kg, portion→L)
- negative quantity rejected at schema level
- repeated conversions (e.g. kg→g→kg across many summed line items) do not accumulate rounding drift the way an equivalent `float` implementation would

Unit tests for `PreparationService.calculate()`:
1. Enough stock → `prepare_quantity <= 0` → no task created.
2. No stock at all → `prepare_quantity == required + safety`.
3. Partial stock → matches worked example above.
4. Safety stock alone (no demand entered) → task still created if stock < safety_stock.
5. Multiple menu items share one preparation product → required quantities sum correctly.
6. Menu item exists with **no** `MenuItemPreparationRequirement` rows → no error, contributes nothing, and is listed as a data-quality warning.
7. Preparation product has no `PreparationRecipe` → calculation still succeeds (recipe not required for shortage calc).
8. Incompatible units in a requirement row → calculation raises a clear, scoped error naming the offending row, not a silent NaN/skip.
9. Duplicate `MenuItemPreparationRequirement` (same menu item + product, two rows) → quantities sum; a warning is also emitted.
10. Empty expected demand for the day → calculation runs without crashing; only safety-stock-driven tasks appear.
11. Historical forecast unavailable (Phase 8+ dependency not yet built) → `DemandService` returns an empty forecast list rather than erroring; `PreparationService` treats it the same as "empty expected demand."
12. Reservation-adjusted demand (Phase 10, forward-looking test) → given a `DemandForecast` row with `source=RESERVATION_ADJUSTED`, `PreparationService` treats it identically to `MANUAL` — the calculation is source-agnostic by design.
13. Recalculating the same `(service_date, service_period)` twice → `NOT_STARTED` tasks are replaced; `IN_PROGRESS`/`COMPLETED` tasks are left untouched and a diff is reported.
14. Manual override recorded on a task → `recommended_quantity` preserved, `final_quantity`/`override_reason`/`overridden_by`/`overridden_at` populated, `recommended_quantity` never mutated.
15. Preparation dependency (one prep product's recipe uses another prep product — Phase 7+) — out of scope for MVP calc, but the schema must not preclude it; tracked as a Phase 7 test, not a Phase 4 one.
16. `LUNCH` and `DINNER` calculated independently for the same `(preparation_product_id, service_date)` → two distinct `PreparationTask` rows, no cross-contamination of `required`/`available`/`prepare_quantity` between periods.
17. `get_current_stock` selects the latest `PreparationStock` row by `recorded_at` at or before the period's planning cutoff, not the day's overall latest row — given a morning snapshot and a later afternoon re-check, `LUNCH` planning (cutoff before the re-check) returns the morning value and `DINNER` planning (cutoff after the re-check) returns the afternoon value.
18. `get_current_stock` with no snapshot at or before the cutoff → returns `0` plus a "never checked" data-quality warning, not an error.

Unit tests for `PriorityService`:
19. Ranking is stable and monotonic in `shortage_score` when all other factors are held equal.
20. A task with `prepare_quantity <= 0` never appears in the actionable (non-READY) list regardless of other factors.
21. **Safety-stock-only task** (`required_quantity = 0`, `safety_stock > current_stock`, e.g. `safety_quantity = 5`, `available = 2` → `prepare_quantity = 3`) → `shortage_score` is computed via the `safety_quantity` branch (§3.2), does **not** raise `ZeroDivisionError`/produce `NaN`/`inf`, and equals `clamp(prepare_quantity / safety_quantity, 0, 1)` (`0.6` in this example) — this is the case the original `prepare_quantity / required_quantity` formula could not handle.
22. Each generated reason line corresponds to an actual contributing sub-score — no reason text for a factor near zero.
23. Changing a single weight (e.g. `w1`) changes only the relative ordering it should plausibly affect — regression-style test with a fixed small fixture of 3–4 tasks.
24. Priority level thresholds are boundary-tested (score exactly at 0.75/0.50/0.25).

Integration tests (Phase 4–6, thin, over a real (test) DB):
25. Full flow: seed catalog → enter demand → enter stock → `POST /preparation/calculate?service_period=DINNER` → `GET /preparation/today?service_period=DINNER` returns correctly shaped, correctly ranked tasks with reasons.
26. Task lifecycle: start → complete with `final_quantity` → `PreparationBatch` row created → task becomes immutable.
