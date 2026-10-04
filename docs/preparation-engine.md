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
POST   /inventory/preparation/snapshot                          # one or more {preparation_product_id, quantity, unit}
                                               # unit may be a container type (SMALL_BOX..XL_BOX) only if an
                                               # active PreparationProductContainerSize already exists for that
                                               # (product, container_type) — rejected otherwise, see §2.5
GET    /inventory/preparation/current?service_date=&service_period=
                                               # resolved stock reading per product, AS THE PLANNING ENGINE
                                               # WOULD SEE IT for that (date, period)'s stock-check window — see §2.4.
                                               # Not an unscoped "latest snapshot" call: the result depends on
                                               # which service period is asking, per data-model.md §5. Both
                                               # params are required, for the same reason service_period is
                                               # required on /preparation/today (no silent defaulting).
                                               # Response per product: {preparation_product_id, status
                                               # (KNOWN|UNKNOWN), quantity, unit, as_of, stale}. This is
                                               # deliberately the same shape PreparationService consumes
                                               # internally, so a dashboard querying this endpoint never
                                               # disagrees with what a calculation run actually used.
                                               # (The Fast Stock-Check screen's separate Phase 2 need —
                                               # "show the last value I entered" while typing a new snapshot —
                                               # is a different, simpler query and is not this endpoint;
                                               # it is designed in Phase 2, not here.)

# Phase 3 — demand
POST   /demand/manual                         # {service_date, service_period, menu_item_id, expected_quantity}
                                               # service_period is required on the body, not optional — a
                                               # DemandForecast without one cannot exist (data-model.md §4)
GET    /demand?service_date=&service_period=  # both required, same reason as /preparation/today: no silent
                                               # defaulting of service_period anywhere in this API (§0/architecture.md)

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
            normalized_qty = convert_for_product(req.preparation_product_id, req.quantity_per_portion, req.unit, canonical_unit(req.preparation_product_id))
                              # convert_for_product, not the plain convert() — handles the rare case where a
                              # requirement is itself expressed in a container unit; see §2.5. Falls through
                              # to plain convert() for the ordinary kg/L/piece/portion case, unchanged.
            required_by_product[req.preparation_product_id] += expected_qty * normalized_qty

    # Step 2 — for every preparation product with a requirement OR existing stock record
    for product in preparation_products where product.id in required_by_product or has_stock_record(product.id):
        required = required_by_product.get(product.id, 0)
        reading = get_current_stock(product.id, service_date, service_period)   # see §2.4 — StockReading, not a bare number
        available = reading.quantity   # 0 when reading.status == UNKNOWN — see §2.4 for why this is still safe
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
                stock_status = reading.status,        # KNOWN | UNKNOWN — see §2.4
                stock_recorded_at = reading.as_of,     # nullable — see §2.4
            )   # upsert key: (preparation_product_id, service_date, service_period) — data-model.md §4
            if reading.status == UNKNOWN:
                add warning: f"{product.name}: stock not checked (or check is stale) as of the {service_period}
                              planning cutoff — prepare_quantity assumes 0 available; verify before relying on it."

    return all tasks for (service_date, service_period), handed to PriorityService for scoring
```

All arithmetic above (`required`, `available`, `safety`, `prepare_quantity`) is `Decimal`, matching the `NUMERIC` columns — see architecture.md §6.

### 2.4 Current Stock Selection and Freshness — `get_current_stock(product_id, service_date, service_period)`

Full semantics (summary in data-model.md §5): "current stock" is **not** the latest `PreparationStock` row for the calendar day, and it is **not** whatever the latest snapshot says regardless of age. Each service period has its **own stock-check window** — a snapshot only counts for a given service if it was recorded *inside that service's window*, not merely "before its cutoff." `get_current_stock` returns a small result type, not a bare number, so callers can never conflate "we checked and there is genuinely none" with "we don't actually know":

```text
StockReading:
    status:    KNOWN | UNKNOWN
    quantity:  Decimal          # the snapshot's quantity when KNOWN; 0 when UNKNOWN (see below for why 0 is safe here)
    as_of:     datetime | null  # recorded_at of the snapshot actually considered; null only when none exists at all
    stale:     bool             # true iff a snapshot exists but was rejected (out of window, or the secondary age check) — status is then UNKNOWN
```

**Why a flat age threshold alone is not enough.** An earlier version of this design used a single `MAX_STOCK_SNAPSHOT_AGE` (e.g. 24h) measured against the cutoff: "latest row at or before cutoff, reject only if older than N hours." That does not actually solve the problem it was meant to solve — a `07:00` morning snapshot is only `~10.5` hours old at a `17:30` DINNER cutoff, so a `24h` threshold would accept it as `KNOWN` for dinner even though lunch service has since consumed stock from it. A single global age cannot distinguish "checked recently" from "checked before the thing that would have changed it" — only a **service-specific window** can, because the window's own boundaries encode "after the point stock last had a reason to change for this service."

**Per-service configured window, not a single cutoff:**

```text
ServiceWindow(service_period):
    stock_check_window_start   # earliest recorded_at that counts as fresh enough for this service
    planning_cutoff             # latest recorded_at that counts, and the moment planning is "as of"

Example configuration (restaurant-specific, core/config.py):
    LUNCH:  stock_check_window_start = 05:00, planning_cutoff = 11:30
    DINNER: stock_check_window_start = 14:00, planning_cutoff = 17:30
        # DINNER's window deliberately starts AFTER lunch service ends, so a
        # morning-only snapshot (recorded before 14:00) cannot satisfy it —
        # only a genuine afternoon re-check can.
```

A `PreparationStock` row is `KNOWN` for `(service_date, service_period)` **only if**:

```text
stock_check_window_start <= recorded_at <= planning_cutoff
```

(both timestamps taken on `service_date` — windows do not span midnight in the MVP; a check recorded just after midnight belongs to the *next* day's windows, not a spillover from the prior night, which is an acceptable simplification for now, not silently handled either way).

```text
get_current_stock(product_id, service_date, service_period):
    window = service_window(service_date, service_period)   # (start, cutoff) — both configured per service_period

    candidate = the PreparationStock row for product_id with the greatest
                recorded_at such that window.start <= recorded_at <= window.cutoff

    if candidate exists:
        # secondary safeguard only — see below; with a sensibly narrow window
        # (a few hours) this practically never triggers, since anything
        # inside the window is already recent by construction
        age = window.cutoff - candidate.recorded_at
        if age > MAX_STOCK_SNAPSHOT_AGE:
            return StockReading(status=UNKNOWN, quantity=0, as_of=candidate.recorded_at, stale=true)
        return StockReading(status=KNOWN,
                             quantity=convert_for_product(product_id, candidate.quantity, candidate.unit, canonical_unit(product_id)),
                             as_of=candidate.recorded_at, stale=false)

    # nothing inside this service's window — look further back only to decide
    # what stock_recorded_at should say (never to supply a usable quantity)
    fallback = the PreparationStock row for product_id with the greatest
               recorded_at such that recorded_at <= window.cutoff   # window.start ignored here
    if fallback exists:
        # e.g. the morning snapshot exists, but it's outside DINNER's window —
        # "checked, but not recently enough for this service", distinct from
        # "never checked at all"
        return StockReading(status=UNKNOWN, quantity=0, as_of=fallback.recorded_at, stale=true)
    else:
        return StockReading(status=UNKNOWN, quantity=0, as_of=null, stale=false)
```

**Why the fallback lookup exists:** `stock_recorded_at` must be `NULL` only when a product has genuinely never been checked (data-model.md §5/§8 integrity rule) — a stale-but-existing morning snapshot must still populate `stock_recorded_at` (with its old timestamp) even though `stock_status = UNKNOWN` for dinner, so the dashboard can say "last checked this morning" rather than just "unknown." This fallback never contributes a *quantity* — only the timestamp used for messaging.

**`MAX_STOCK_SNAPSHOT_AGE` is retained, demoted to a secondary safeguard, not the primary rule.** With sensibly narrow windows (a few hours wide), anything that falls inside a window is already recent by construction, so this check is expected to rarely if ever trigger in practice — it exists purely as defense-in-depth against a misconfigured, unrealistically wide window (e.g. someone sets a window 30 hours wide by mistake). The **service-specific window is the primary rule**, per this correction.

**Why the window boundaries, not wall-clock `now`, decide freshness:** exactly as before (unchanged principle) — `PreparationService.calculate()` must be pure (§2.1). `window.start`/`window.cutoff` are deterministic functions of `(service_date, service_period)` and restaurant config, never of when `calculate()` happens to run, so recalculating the same `(service_date, service_period)` later never flips the result just because time passed.

**This is exactly the scenario the correction calls out, worked through:**

```text
Config: LUNCH window [05:00, 11:30], DINNER window [14:00, 17:30]

morning snapshot recorded 07:00
    -> LUNCH:  07:00 is inside [05:00, 11:30]           -> KNOWN, quantity = morning snapshot
    -> DINNER: 07:00 is NOT inside [14:00, 17:30]        -> not a candidate for dinner

lunch service consumes stock (not recorded automatically — MVP has no auto-decrement)

-- no afternoon re-check recorded --
    -> DINNER: no candidate in [14:00, 17:30]; fallback finds the 07:00 row (<= 17:30)
               -> UNKNOWN, stale=true, as_of=07:00   ("checked this morning, not since lunch")

-- afternoon re-check recorded 16:00 --
    -> DINNER: 16:00 is inside [14:00, 17:30]            -> KNOWN, quantity = afternoon snapshot, as_of=16:00
```

`LUNCH` planning is entirely unaffected by whether an afternoon re-check ever happens, because `16:00` falls outside `LUNCH`'s own window — each service resolves independently from its own window, never from "whatever the latest row happens to be." This also means recording a stock snapshot *during* dinner service does not retroactively corrupt a dinner plan that already ran, because that calculation already used whatever was in-window at the time and its `PreparationTask` row is not silently recalculated (§2.3 recalculation rule).

**Why `available = 0` on `UNKNOWN`, not "skip the product" or "error":** the arithmetic still needs a number to compute `prepare_quantity`, and assuming zero available stock is the conservative direction — it can only over-estimate `prepare_quantity`, never under-estimate it, so an unknown-stock product still gets surfaced on the prep list rather than silently dropped. What must never happen is presenting that assumed `0` as if it were a confirmed stock check; that is exactly why `stock_status`/`stock_recorded_at` travel with the task (see data-model.md §5) and why the UI/`reason_text` must say "not checked" rather than "0 available" when `stock_status = UNKNOWN`. This correction does **not** change `PriorityService` — an `UNKNOWN` task is not automatically boosted in priority; that is left as a possible future refinement, not built now.

### 2.3 Edge cases (explicit, not accidental)

- **Menu item with no preparation mapping** → contributes 0 to every product; does not error; flagged in a warnings list returned alongside tasks (visible to chef, not hidden).
- **Preparation product with no recipe** → irrelevant to this calculation (recipes are Phase 7 / raw ingredient layer); shortage calc doesn't require a recipe to exist.
- **No expected demand entered for the day** → `required_by_product` is empty; the calculation still runs and creates tasks *only* for products with negative safety-vs-stock coverage (i.e., simply low on standing safety stock), so the system still surfaces "you're below safety stock" even before anyone enters covers.
- **Same preparation product used by multiple menu items** → summed in Step 1 by construction (spec §10, §28's Dish A example).
- **Duplicate `MenuItemPreparationRequirement` rows** (same menu_item + same product) → summed rather than rejected at calc time, but flagged as a data-quality warning; uniqueness should also be enforced at write time in `POST /menu-items/{id}/preparation-requirements` to prevent accidental duplicates in the first place.
- **Incompatible units** (e.g., recipe says `piece`, but product's canonical unit is `kg`) → `convert()` raises `IncompatibleUnitError`; the calculation fails loudly for that one line item (surfaced as a data error to fix in the catalog), it does not silently guess or drop the term.
- **Recalculation** (`POST /preparation/calculate` called twice for the same `(date, service_period)`) → upsert semantics on `(preparation_product_id, service_date, service_period)`; a task already `IN_PROGRESS`/`COMPLETED` is **not** silently overwritten — recalculation only touches `NOT_STARTED` tasks and reports a diff for the rest ("required quantity changed from 10kg to 12kg for Bratkartoffeln, already in progress — review manually").
- **Same product, different service periods on the same day** → `LUNCH` and `DINNER` tasks for the same `preparation_product_id`/`service_date` are independent rows (different `service_period`), each with its own `get_current_stock` cutoff (§2.4); they are never merged or compared to each other by the calculation.
- **Stock snapshot exists but falls outside this service's window** (recorded before `stock_check_window_start`, or — rarely, as a secondary safeguard — inside the window but exceeding `MAX_STOCK_SNAPSHOT_AGE`) → treated identically to "no snapshot at all" for arithmetic: `stock_status = UNKNOWN`, `available_quantity` forced to `0`, a warning attached, and `stock_recorded_at` still records *when* that out-of-window snapshot was taken so the chef can see how out of date it is — never silently trusted as current (§2.4). A morning-only snapshot with no afternoon re-check is the canonical example: valid for `LUNCH`, `UNKNOWN` for `DINNER`.

### 2.5 Container / Display Unit Conversion (product-specific, spec addendum)

Kitchen quantities are not always kg/L/piece/portion — many Step-2 preparation products are thought of in physical containers (`SMALL_BOX`/`MEDIUM_BOX`/`LARGE_BOX`/`XL_BOX`, fractional counts allowed: `0.5 XL_BOX`), and **the size a box represents is product-specific, never a global constant** (data-model.md §9 — `1 XL_BOX` of Krautsalat ≠ `1 XL_BOX` of Kartoffelsalat). This section defines where that conversion happens and, critically, keeps it entirely out of the priority scoring path (§3.2).

**Product-aware conversion wraps the plain, product-agnostic `core/units.py convert()`, it does not replace it:**

```text
convert_for_product(preparation_product_id, quantity, from_unit, to_unit) -> Decimal:
    if from_unit is not a container type and to_unit is not a container type:
        return convert(quantity, from_unit, to_unit)   # unchanged, dimension-checked, no DB access

    # at least one side is a container type — resolve via PreparationProductContainerSize
    to_measurable(unit, qty):
        if unit is a container type:
            row = get_active_container_size(preparation_product_id, unit)   # data-model.md §9
            if row is None:
                raise NoVerifiedContainerConversionError(preparation_product_id, unit)
            return qty * row.equivalent_quantity, row.equivalent_unit
        return qty, unit

    measurable_qty, measurable_unit = to_measurable(from_unit, quantity)

    if to_unit is a container type:
        row = get_active_container_size(preparation_product_id, to_unit)
        if row is None:
            raise NoVerifiedContainerConversionError(preparation_product_id, to_unit)
        return convert(measurable_qty, measurable_unit, row.equivalent_unit) / row.equivalent_quantity
    else:
        return convert(measurable_qty, measurable_unit, to_unit)
```

**Where the "no verified conversion yet" case is handled differently depending on which side of the system hits it — this asymmetry is deliberate:**

- **Write-time (input), fail early and clearly.** `POST /inventory/preparation/snapshot` and `POST /menu-items/{id}/preparation-requirements` validate immediately: if the submitted `unit` is a container type, an *active* `PreparationProductContainerSize` must already exist for that `(preparation_product_id, container_type)`, or the write is rejected with a clear, actionable error ("no verified `XL_BOX` conversion for Krautsalat yet — record this snapshot in `kg`/`L`/`piece`/`portion` instead, or verify the container size first"). This is a **recommended refinement over doing the check only at calculation time**: it puts the failure at the earliest, most actionable moment (a worker mid-stock-check can immediately switch units) rather than surfacing it minutes or hours later inside a `PreparationService.calculate()` run, and it means `calculate()` itself never needs a "missing container conversion" failure path for stored data — by construction, any container-unit quantity already in the database has a verified conversion.
- **Read-time (display), degrade gracefully.** `PreparationProduct.preferred_prep_unit` may legitimately be set to a container type *before* its conversion is verified (a kitchen stating intent ahead of physically weighing a box — data-model.md §9). Rendering `prepare_quantity` (always stored/computed in canonical units) in `preferred_prep_unit` for display must **not** error or block the dashboard — the single most important screen in the system (spec §13) must never go down because of an unverified conversion. If `get_active_container_size` returns nothing, the display falls back to the canonical unit with a small note ("container size not yet verified — showing kg").

**Worked example (matches the restaurant's own description):**

```text
Krautsalat.default_unit = kg
Krautsalat.preferred_prep_unit = XL_BOX
PreparationProductContainerSize: Krautsalat / XL_BOX -> equivalent_quantity=8.500, equivalent_unit=kg (verified)

PreparationService computes, entirely in kg: prepare_quantity = 8.7 kg
Dashboard renders: "Prepare: 8.7 kg (≈ 1 XL_BOX)"
    convert_for_product(Krautsalat.id, 8.7, kg, XL_BOX) = 8.7 / 8.5 ≈ 1.02 → displayed rounded as "≈ 1 XL_BOX"
```

**What this section explicitly does not touch:** `PriorityService` (§3.2). `shortage_score`'s `target_quantity`/`prepare_quantity` are always compared *within one task* (same product, same unit — a dimensionless ratio regardless of which unit that happens to be), so container units never cause a problem there. What container units *would* break, if allowed to leak in, is any sub-score that compares raw quantities *across* tasks/products — which is exactly the `demand_score` bug fixed in §3.2 (`expected_usage_count`, not `required_quantity`). The rule going forward: **container/display units answer "how much should we prepare"; `expected_usage_count` answers "how in-demand is this product" — a priority sub-score must never read a physical quantity value across products, in any unit.**

## 3. Priority Algorithm (explainable, spec §11)

### 3.1 Principle

No opaque AI score. Every factor is a named, independently-computed sub-score in `[0, 1]`, combined with configurable weights, and every task carries the human-readable reasons that produced its score.

### 3.2 Sub-scores

```text
shortage_score:
    target_quantity = required_quantity + safety_quantity
        # NOTE: "target_quantity" here is this calculation's own derived sum
        # (today's required demand + this product's standing safety stock).
        # It is NOT the same thing as PreparationProduct.target_stock, which
        # is a separate, independently-configured field (a chef-set stock
        # goal). Do not conflate the two when implementing — name the local
        # variable target_quantity, not target_stock, to keep them visually
        # distinct in code as well as in this doc.

    if target_quantity > 0:
        shortage_score = clamp(prepare_quantity / target_quantity, 0, 1)
        # 1.0 = prepare_quantity == target_quantity, i.e. available == 0 —
        #       nothing on hand toward either demand or safety stock.
        # 0.0 = prepare_quantity <= 0 — fully covered (this task wouldn't
        #       exist in the first place; included for completeness).
        # This single formula covers ordinary demand tasks (safety_quantity
        # contributes a small, usually-nonzero term to the denominator),
        # safety-stock-only tasks (required_quantity == 0, so
        # target_quantity == safety_quantity), and everything in between —
        # no separate branch needed.
    else:
        # required_quantity == 0 and safety_quantity == 0: prepare_quantity
        # cannot be positive here (prepare_quantity = required + safety -
        # available, and available >= 0), so a task would not have been
        # created for this product at all. Defined for completeness only.
        shortage_score = 0

demand_score:
    expected_usage_count = sum, over every menu item that requires this preparation product
                            (per MenuItemPreparationRequirement), of that menu item's
                            expected_quantity for this (service_date, service_period)
        # a COUNT of expected orders/portions across dependent dishes — unitless by
        # construction. NOT required_quantity: required_quantity is a physical quantity
        # (kg, L, piece, portion, or a container unit — see §2.5/§9) that differs in
        # *dimension* from product to product, so comparing required_quantity across
        # today's tasks (as an earlier version of this doc did) silently compares kg
        # against L against pieces against boxes — meaningless. expected_usage_count
        # is dimensionless (a count of orders), so it can be safely compared/normalized
        # across every task regardless of what unit each product is measured in.

    demand_score = normalize(expected_usage_count against today's distribution of
                              expected_usage_count across all tasks — e.g. percentile rank)

dependency_score       = normalize(count of distinct menu items requiring this product
                                     against max dependency count today)

prep_time_score        = normalize(prep_time_minutes against max prep_time_minutes today)
                         # longer prep → start sooner → higher score

emergency_difficulty_score = product.difficulty_score (0-1, pre-configured per product;
                         "how bad is it to make this last-minute / mid-service")

priority_score = shortage_score   * w1
               + demand_score     * w2
               + dependency_score * w3
               + prep_time_score  * w4
               + emergency_difficulty_score * w5

# w1..w5 configurable, default (sum = 1.0):
w1=0.40 (shortage)  w2=0.15 (demand)  w3=0.15 (dependency)
w4=0.20 (prep_time) w5=0.10 (emergency difficulty)
```

**`urgency_score` is removed from the MVP algorithm** (it appeared in earlier drafts of this doc as `based on earliest_expected_need vs. now`). Two independent problems made it unusable as specified, not just under-specified:

1. **No reliable input exists.** `earliest_expected_need` is not a field anywhere in the Phase 1–7 data model (data-model.md) — there is no per-task expected-order-time to compute urgency from. Introducing a fabricated or hardcoded stand-in would violate spec §35's "AI should assist but not control core arithmetic" posture just as much as a guess would.
2. **"vs. now" conflicts with the determinism requirement this doc establishes elsewhere.** §2.4 explicitly measures stock-snapshot age against the deterministic `cutoff`, not wall-clock time, specifically so `PreparationService.calculate()` stays pure (same inputs → same output, spec §10/§29). A `urgency_score` defined against wall-clock `now` would make `PriorityService`'s output non-reproducible on re-run — the same inconsistency the freshness design in §2.4 was written to avoid, just recreated one section later.

**Weight redistribution (not an even split):** the freed `0.10` is not spread evenly — `prep_time_score` absorbs most of it (`0.15 → 0.20`) because it is the sub-score that most overlaps urgency's intended role: a long-prep item genuinely does need to start earlier, without requiring a precise deadline to say so. `shortage_score` keeps its dominant weight (`0.35 → 0.40`, absorbing a small remainder) since it remains the single strongest signal ("how empty are we, right now"). `demand_score`, `dependency_score`, and `emergency_difficulty_score` are left at their prior values, since none of them were proxying for urgency in the first place.

**Reintroduction condition:** `urgency_score` can come back once real order-time-of-day data exists (Phase 8+ `OrderHistory`, or Phase 9 forecasting) to derive an actual `earliest_expected_need` per task — at that point it re-enters as `w6`, and weights are redistributed again. Not scheduled before then.

**Why `demand_score` was changed from `required_quantity` to `expected_usage_count`:** this is a correction to the original Phase 0 design, not a new feature — it was already latent before container units existed (a `kg`-measured task and a `piece`-measured task were already being percentile-ranked against each other on raw quantity), and the introduction of product-specific container units (§2.5/§9) makes the bug impossible to ignore (a `0.5 XL_BOX` task ranked by raw magnitude against an `8 kg` task is obviously nonsensical). The fix generalizes: **container/display units answer "how much should we prepare," `expected_usage_count` answers "how in-demand is this product today" — the two must never be conflated.** `dependency_score` (count of *distinct* menu items requiring the product — a static, catalog-level breadth measure) and `demand_score`/`expected_usage_count` (today's *actual order volume* across those dependent menu items — a dynamic, per-service-date depth measure) are related but distinct and both dimensionless; neither one, nor any other priority sub-score, may read a `PreparationTask`/`PreparationStock` quantity value directly across products. `expected_usage_count` is computed at scoring time from the same `DemandForecast`/`MenuItemPreparationRequirement` join `PreparationService.calculate()` already performs (§2.2) — it is not a persisted column, exactly like every other sub-score.

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
- only 25% of target stock (demand + safety) is available   (shortage_score contribution)
- used by 4 menu items                        (dependency_score contribution)
- expected demand is high                     (demand_score contribution)
- preparation takes 45 minutes                (prep_time_score contribution)
```

`reason_text` on `PreparationTask` stores this generated explanation (plain text, regenerated on every calculation — never hand-edited, since it must always match the score that produced it).

### 3.5 Explicitly not doing (per spec §35)

- No ML-based/learned scoring for MVP. Weights are static config, tuned by a human, not fit from data, until Phase 13 at the earliest.
- No LLM in the scoring path. LLMs are only usable later for voice intent parsing (Phase 11) and natural-language summaries of an already-computed dashboard — never to produce the score itself.
- No `urgency_score` for MVP — no reliable `earliest_expected_need` input exists yet, and scoring against wall-clock "now" would break the reproducibility this doc requires elsewhere (§2.4, §3.2). Reintroduced once real order-time data exists (Phase 8+).

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

Unit tests for `convert_for_product` (§2.5):
- Two different products with an active `XL_BOX` conversion each (e.g. Krautsalat `8.5 kg`, Kartoffelsalat `6.0 kg`) → converting `1 XL_BOX` for each returns the *product's own* `equivalent_quantity`, never a shared/global value — this is the core guarantee of the feature.
- Fractional container quantities round-trip correctly: `0.5 XL_BOX` and `1.5 LARGE_BOX` convert to/from the canonical unit without rounding to a whole box.
- Converting a container unit for a product with **no active conversion row** raises `NoVerifiedContainerConversionError` — never silently falls back to a guessed value.
- `equivalent_unit` differing in scale from the requested target (e.g. conversion stored in `kg`, caller wants `g`) still resolves correctly by chaining through the plain `convert()` — §2.5's algorithm.
- A container-to-container conversion is never attempted directly (e.g. `LARGE_BOX` → `XL_BOX`); the algorithm always routes through the product's canonical/measurable unit first.

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
17. **The exact scenario this correction is about.** Config: `LUNCH` window `[05:00, 11:30]`, `DINNER` window `[14:00, 17:30]`. Record one `PreparationStock` snapshot at `07:00`. Assert `get_current_stock(product, service_date, LUNCH)` → `StockReading(status=KNOWN, ...)` using the `07:00` value. Assert `get_current_stock(product, service_date, DINNER)` (no further snapshot recorded) → `StockReading(status=UNKNOWN, quantity=0, as_of=07:00, stale=true)` — the morning check must **not** carry over to dinner. Then record a second snapshot at `16:00` and re-assert `get_current_stock(product, service_date, DINNER)` → `StockReading(status=KNOWN, ...)` using the `16:00` value, and that `LUNCH`'s earlier result is unaffected by the 16:00 row's existence.
18. `get_current_stock` with no `PreparationStock` row at all before either window's cutoff → returns `StockReading(status=UNKNOWN, quantity=0, as_of=null, stale=false)` plus a "never checked" data-quality warning, not an error — distinct from item 17's "checked, but not for this service" case (`as_of` populated vs. `null`).
19. **Secondary safeguard** — a snapshot that falls inside a service's window but still exceeds `MAX_STOCK_SNAPSHOT_AGE` (only reachable with an unrealistically wide window, e.g. a misconfigured 30-hour `DINNER` window) → still resolves to `StockReading(status=UNKNOWN, ..., stale=true)`. Confirms the age check remains a functioning backstop even though the window is expected to make it redundant under normal configuration.
20. **`AVAILABLE = 0` vs `STOCK UNKNOWN` are distinguishable** — two tasks built from otherwise-identical inputs (`required`, `safety`) but one from a *fresh, in-window* snapshot that literally reads `quantity = 0` (`stock_status = KNOWN`) and one from *no in-window snapshot* (`stock_status = UNKNOWN`) must produce the same `prepare_quantity` (both treat available as 0 arithmetically) but different `stock_status`/`reason_text` — the fresh-zero case never gets the "not checked, verify before relying on this" warning, the unknown case always does.
21. Recalculating the same `(service_date, service_period)` after a previously-out-of-window snapshot is superseded by a fresh in-window one (e.g. the `16:00` re-check in item 17, recorded after an earlier `DINNER` calculation already ran as `UNKNOWN`) → the next `NOT_STARTED`-task recalculation flips `stock_status` from `UNKNOWN` back to `KNOWN` and recomputes `available_quantity` accordingly (this is calculation-time re-evaluation, not a mutation of history — see §2.3 recalculation rule).

Unit tests for `PriorityService`:
22. Ranking is stable and monotonic in `shortage_score` when all other factors are held equal.
23. A task with `prepare_quantity <= 0` never appears in the actionable (non-READY) list regardless of other factors.
24. **`shortage_score` — normal demand + safety stock**: `required_quantity = 2.0`, `safety_quantity = 0.2`, `available = 0.5` → `prepare_quantity = 1.7`, `target_quantity = 2.2` → `shortage_score = clamp(1.7 / 2.2, 0, 1) ≈ 0.773`.
25. **`shortage_score` — safety-stock-only task**: `required_quantity = 0`, `safety_quantity = 5`, `available = 2` → `prepare_quantity = 3`, `target_quantity = 5` → `shortage_score = clamp(3 / 5, 0, 1) = 0.6`; must **not** raise `ZeroDivisionError`/produce `NaN`/`inf` — this is the case the original `prepare_quantity / required_quantity` formula could not handle.
26. **`shortage_score` — zero target**: `required_quantity = 0`, `safety_quantity = 0` → `target_quantity = 0` → `shortage_score = 0` via the explicit `else` branch (§3.2), regardless of `prepare_quantity` (which is `<= 0` here by construction, so no task exists in practice — this test exercises the function directly for completeness).
27. **`shortage_score` — completely empty stock**: `available = 0`, `required_quantity = 4.0`, `safety_quantity = 1.0` → `prepare_quantity = target_quantity = 5.0` → `shortage_score = clamp(5.0 / 5.0, 0, 1) = 1.0` (fully uncovered).
28. **`shortage_score` — partially covered target**: `required_quantity = 4.0`, `safety_quantity = 1.0` (`target_quantity = 5.0`), `available = 3.0` → `prepare_quantity = 2.0` → `shortage_score = clamp(2.0 / 5.0, 0, 1) = 0.4`.
29. Each generated reason line corresponds to an actual contributing sub-score — no reason text for a factor near zero.
30. Changing a single weight (e.g. `w1`) changes only the relative ordering it should plausibly affect — regression-style test with a fixed small fixture of 3–4 tasks.
31. Priority level thresholds are boundary-tested (score exactly at 0.75/0.50/0.25).
32. **`demand_score` uses `expected_usage_count`, not raw `required_quantity`, and ranks correctly across mixed units** — three tasks with `required_quantity` `0.5 XL_BOX` (Krautsalat), `9.0 kg` (Bratkartoffeln), and `3 piece` (a portioned item) must be rankable by `demand_score` at all without a unit-conversion error or a meaningless magnitude comparison; construct `expected_usage_count` directly (e.g. `12`, `40`, `5` expected orders respectively) and assert `demand_score` ranks by that count, not by which raw quantity happens to look numerically larger.

Integration tests (Phase 4–6, thin, over a real (test) DB):
33. Full flow: seed catalog → enter demand → enter stock → `POST /preparation/calculate?service_period=DINNER` → `GET /preparation/today?service_period=DINNER` returns correctly shaped, correctly ranked tasks with reasons.
34. Task lifecycle: start → complete with `final_quantity` → `PreparationBatch` row created → task becomes immutable.
35. `GET /inventory/preparation/current?service_date=&service_period=` returns, for a given product, the same `status`/`quantity`/`as_of` that the corresponding `POST /preparation/calculate` run for that exact `(service_date, service_period)` used internally — the two code paths must not disagree.
36. `POST /inventory/preparation/snapshot` with a container-type `unit` and no active `PreparationProductContainerSize` for that product/container combination → rejected (4xx) with a clear message naming the missing conversion, not accepted and failed later at calculation time (§2.5).
37. Dashboard rendering with `PreparationProduct.preferred_prep_unit` set to a container type that has **no** active conversion yet → renders the canonical-unit value with a "not yet verified" note; does not error, and does not block the rest of the dashboard from rendering (§2.5).
