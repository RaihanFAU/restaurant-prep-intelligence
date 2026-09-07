# Restaurant Preparation Intelligence System

## Project Overview

This project is a **Restaurant Preparation Intelligence System** for traditional German restaurants that prepare a large amount of food from scratch.

The main operational problem is not simply raw inventory management.

The central problem is:

> **Before service starts, the kitchen must know what preparation products are missing, how much must be prepared, and what should be prepared first.**

The system should reduce:

- forgotten preparation items
- emergency preparation during service
- manual stock-checking time
- service delays
- kitchen stress
- unnecessary over-preparation
- food waste

The initial target environment is a traditional German restaurant similar to Das Humbser in Fürth.

Reference menu:

https://www.dashumbser.de/karte

---

# 1. Core Domain Concept

The system has three operational levels.

## Level 1 — Menu Items / Expected Demand

These are dishes customers order.

Examples:

- Wiener Schnitzel
- Schäuferle
- Krustenbraten
- Zwiebelrostbraten
- Backfisch
- Buttermilch Hendl
- Käsespätzle
- soups
- salads
- desserts

The system must estimate or receive expected demand for menu items.

Initially this will be entered manually.

Later it may come from:

- historical POS orders
- reservations
- weekday patterns
- seasonal patterns
- restaurant software integrations

---

## Level 2 — Preparation Products

This is the most important level for the MVP.

These are products or components the kitchen prepares before service.

Examples:

- Bratkartoffeln
- Kartoffelsalat
- Krautsalat
- Gurkensalat
- Salatdressing
- Jus
- Remoulade
- Spätzle
- Klöße
- Kartoffelpüree
- Rotkraut
- Sauerkraut
- Rahmspinat
- prepared fish
- prepared chicken
- Schnitzel
- prepared vegetables
- sauces
- onions
- dessert components
- brownies
- apple crumble
- ice cream portions

The handwritten kitchen sheets supplied for this project represent mostly these **Step-2 preparation products**, not raw ingredients.

These preparation products are what workers need to check before service.

---

## Level 3 — Raw Ingredients

Raw ingredients are required to create preparation products.

Examples:

- potatoes
- onions
- eggs
- milk
- cream
- butter
- flour
- meat
- fish
- cabbage
- carrots
- herbs
- spices
- oil
- vinegar

Raw ingredient management is important, but it is not the main focus of the first MVP.

---

# 2. Primary Workflow

The main workflow is:

```text
Expected Menu Demand
        ↓
Menu Item Requirements
        ↓
Required Preparation Products
        ↓
Current Prepared Stock
        ↓
Shortage Calculation
        ↓
Priority Calculation
        ↓
Final Kitchen Preparation List
```

Optional second-stage workflow:

```text
Preparation Product Shortage
        ↓
Preparation Recipe
        ↓
Raw Ingredients Required
        ↓
Raw Ingredient Availability
        ↓
Can We Prepare It?
```

---

# 3. Business Problems

## Problem 1 — Forgotten Preparation

Sometimes a preparation product is forgotten.

Example:

A customer orders a dish that requires:

- meat
- sauce
- potato component
- vegetables

The kitchen discovers during service that one component was not prepared.

Consequences:

- service delay
- lost concentration
- worker stress
- inconsistent food timing
- customer waiting

The system should identify this risk before service starts.

---

## Problem 2 — Manual Stock Checking

Workers currently may need to manually inspect:

- freezers
- refrigerators
- Kühlhaus
- preparation stations
- shelves
- containers
- dry-storage areas

They manually write down:

- what exists
- how much exists
- what is missing
- how much must be prepared

This is slow and error-prone.

The new system should make this stock-check workflow extremely fast.

---

## Problem 3 — Preparation Priority

Not every missing preparation item has equal importance.

The system should answer:

> **What should I prepare next?**

Priority should consider:

- shortage severity
- how many dishes depend on the component
- expected demand
- historical usage
- preparation time
- earliest expected need
- current stock coverage
- safety stock
- dependency on other preparation products
- emergency preparation difficulty

---

## Problem 4 — Multilingual Kitchen

The application should initially support:

- English
- German

The architecture should make more languages easy to add later.

---

## Problem 5 — Voice Interaction

Kitchen workers may have wet or dirty hands.

They should eventually be able to say commands such as:

### German

- "Wie viel Rotkohl haben wir?"
- "Wir haben noch drei Kilo Rotkohl."
- "Was muss ich als Nächstes vorbereiten?"
- "Markiere Bratkartoffeln als fertig."
- "Wir haben keine Aioli mehr."

### English

- "How much red cabbage do we have?"
- "We have three kilos of red cabbage."
- "What should I prepare next?"
- "Mark roast potatoes as completed."
- "We have no aioli left."

Voice support should not be required for the first MVP.

---

# 4. MVP Goal

The first working version should be testable manually.

Do not depend on E2N, POS APIs, Resmio, or machine learning initially.

The MVP should allow the user to:

1. define menu items
2. define preparation products
3. map menu items to preparation products
4. enter expected menu demand manually
5. enter current prepared quantities manually
6. calculate required preparation quantities
7. calculate shortages
8. rank preparation tasks by priority
9. show a preparation dashboard
10. mark tasks as completed

---

# 5. Important Product Principle

This is **not primarily an inventory application**.

It is:

> **A restaurant preparation decision-support system.**

Inventory data exists mainly to answer:

- What must be prepared?
- How much must be prepared?
- What should be prepared first?
- Are we ready for service?

---

# 6. Example

Assume expected dinner demand includes 40 Schnitzel.

Each Schnitzel requires:

- 250 g Bratkartoffeln
- 1 salad portion
- 80 ml sauce

Required Bratkartoffeln:

```text
40 × 250 g = 10 kg
```

Current prepared stock:

```text
3 kg
```

Safety stock:

```text
1 kg
```

Required preparation:

```text
10 + 1 - 3 = 8 kg
```

Dashboard:

```text
Bratkartoffeln
Required: 10 kg
Available: 3 kg
Safety: 1 kg
Prepare: 8 kg
```

---

# 7. Preparation Statuses

Preparation products should support statuses such as:

- READY
- LOW
- EMPTY
- NOT_STARTED
- IN_PROGRESS
- BLOCKED
- COMPLETED

---

# 8. Core Entities

The application should have clear separation between menu items, preparation products, and raw ingredients.

Suggested entities:

## MenuItem

Represents a dish sold to customers.

Suggested fields:

```text
id
name_de
name_en
category
is_active
created_at
updated_at
```

---

## PreparationProduct

Represents a Step-2 preparation product.

Suggested fields:

```text
id
name_de
name_en
category
default_unit
storage_location_id
minimum_stock
target_stock
safety_stock
prep_time_minutes
shelf_life_hours
difficulty_score
is_active
created_at
updated_at
```

---

## RawIngredient

Suggested fields:

```text
id
name_de
name_en
category
default_unit
storage_location_id
minimum_stock
is_active
created_at
updated_at
```

---

## MenuItemPreparationRequirement

Maps menu items to preparation products.

Example:

```text
Wiener Schnitzel
    -> Kartoffelsalat: 250 g
    -> Gurkensalat: 1 portion
    -> Preiselbeeren: 30 g
```

Suggested fields:

```text
id
menu_item_id
preparation_product_id
quantity_per_portion
unit
```

---

## PreparationRecipe

Defines how a preparation product is produced.

Example:

```text
Kartoffelsalat
    -> potatoes
    -> onions
    -> vinegar
    -> oil
    -> seasoning
```

Suggested fields:

```text
id
preparation_product_id
yield_quantity
yield_unit
instructions
version
is_active
```

---

## PreparationRecipeIngredient

Suggested fields:

```text
id
preparation_recipe_id
raw_ingredient_id
quantity
unit
```

---

## PreparationStock

Tracks current prepared stock.

Suggested fields:

```text
id
preparation_product_id
quantity
unit
recorded_at
recorded_by
```

---

## RawIngredientStock

Suggested fields:

```text
id
raw_ingredient_id
quantity
unit
recorded_at
recorded_by
```

---

## PreparationTask

Suggested fields:

```text
id
preparation_product_id
service_date
required_quantity
available_quantity
safety_quantity
prepare_quantity
unit
priority_score
priority_level
status
reason_text
created_at
started_at
completed_at
completed_by
```

---

## PreparationBatch

Tracks actual produced quantities.

Suggested fields:

```text
id
preparation_product_id
quantity
unit
prepared_at
prepared_by
task_id
```

---

## StorageLocation

Examples:

- freezer
- refrigerator
- Kühlhaus
- dry storage
- kitchen station
- sauce station
- dessert station

Suggested fields:

```text
id
name
description
```

---

## DemandForecast

Suggested fields:

```text
id
service_date
menu_item_id
expected_quantity
source
confidence_low
confidence_high
created_at
```

Sources could include:

- MANUAL
- HISTORICAL
- RESERVATION_ADJUSTED
- ML

---

## Reservation

Suggested fields:

```text
id
reservation_date
reservation_time
guest_count
status
source
external_id
```

---

## OrderHistory

Suggested fields:

```text
id
ordered_at
menu_item_id
quantity
source
external_id
```

---

## WasteRecord

Suggested fields:

```text
id
preparation_product_id
quantity
unit
reason
recorded_at
```

---

# 9. Units

Quantity handling must be safe.

Supported units should include:

- kg
- g
- L
- ml
- piece
- portion
- tray
- container

Allowed conversions:

```text
1 kg = 1000 g
1 L = 1000 ml
```

Never automatically convert incompatible units.

Examples of incompatible dimensions:

- kg to liters
- pieces to kilograms
- portions to liters

unless an explicit recipe conversion exists.

---

# 10. Preparation Calculation

Use deterministic calculations.

Basic formula:

```text
required_quantity =
expected_menu_demand
×
quantity_per_portion
```

When multiple menu items use the same preparation product:

```text
total_required_quantity =
sum(required quantity across all menu items)
```

Then:

```text
prepare_quantity =
total_required_quantity
+ safety_stock
- current_available_quantity
```

If:

```text
prepare_quantity <= 0
```

then:

```text
NO PREPARATION REQUIRED
```

Otherwise create a preparation task.

---

# 11. Priority Algorithm

The priority system must be explainable.

Do not use an opaque AI score.

Suggested configurable factors:

```text
shortage_severity
expected_consumption
number_of_dependent_menu_items
historical_usage_frequency
preparation_time
earliest_expected_need
current_stock_coverage
safety_stock_risk
dependency_importance
emergency_preparation_difficulty
```

Initial conceptual score:

```text
priority_score =
    shortage_score * w1
  + demand_score * w2
  + dependency_score * w3
  + prep_time_score * w4
  + urgency_score * w5
  + emergency_difficulty_score * w6
```

Weights must be configurable.

Priority levels:

- CRITICAL
- HIGH
- NORMAL
- LOW

Every task should show an explanation.

Example:

```text
Jus — CRITICAL

Reasons:
- only 25% of required stock is available
- used by 4 menu items
- expected demand is high
- preparation takes 45 minutes
```

---

# 12. Fast Stock Check Screen

This is one of the most important UI screens.

It should be optimized for mobile/tablet use.

Example:

```text
TODAY'S STOCK CHECK

Bratkartoffeln
Current:
[ 4.5 ] kg

Rotkohl
Current:
[ 3.0 ] kg

Jus
Current:
[ 2.0 ] L

Salatdressing
Current:
[ 1.5 ] L
```

Requirements:

- large touch-friendly controls
- numeric input
- minimal clicks
- autosave where appropriate
- previous quantity visible
- expected requirement visible
- low-stock warnings
- search
- category grouping
- optional voice input later

---

# 13. Preparation Dashboard

Example:

```text
TODAY — DINNER PREPARATION

CRITICAL

1. Bratkartoffeln
   Available: 3 kg
   Required: 11 kg
   Prepare: 8 kg
   Prep time: 45 min

2. Jus
   Available: 2 L
   Required: 6 L
   Prepare: 4 L
   Prep time: 45 min

HIGH

3. Krautsalat
   Prepare: 2 kg

4. Salatdressing
   Prepare: 1.5 L

READY

✓ Sauerkraut
✓ Remoulade
✓ Kartoffelsalat
```

The UI should answer:

> **What should I prepare next?**

within seconds.

---

# 14. Manual Override

Chef judgement must always be possible.

Example:

```text
System recommends:
8 kg Bratkartoffeln

Chef chooses:
10 kg
```

Store:

```text
recommended_quantity
final_quantity
override_reason
overridden_by
overridden_at
```

---

# 15. Historical Demand

After the manual MVP works, import previous order history.

Start with CSV.

Analyze:

- weekday demand
- hourly demand
- dish popularity
- average portions
- recent trends
- seasonal patterns

Start with simple statistical methods:

- weekday averages
- moving averages
- weighted averages

Do not start with complex machine learning.

---

# 16. Reservations

Reservations should improve expected covers.

Example:

```text
Typical Thursday dinner:
80 guests

Today's reservations:
120 guests
```

The system can scale expected demand.

Reservations do not tell us exactly what people will order.

Use:

```text
expected covers
×
historical dish distribution
```

Example:

```text
120 expected guests

Historical distribution:
35% Schnitzel
15% fish
10% salad
...
```

This produces estimated menu demand.

---

# 17. External Integrations

The application must not be tightly coupled to a restaurant system.

Create provider interfaces.

Example:

```text
ReservationProvider
OrderHistoryProvider
```

Possible implementations:

```text
ManualReservationProvider
CSVReservationProvider
ResmioReservationProvider
E2NReservationProvider
```

and:

```text
ManualOrderProvider
CSVOrderProvider
E2NOrderProvider
POSOrderProvider
```

Use official APIs, webhooks, exports, or CSV when available.

Do not scrape protected systems.

---

# 18. E2N / POS / Reservation Integration Strategy

Do not integrate this during the first MVP.

Recommended phases:

```text
Phase A
Manual expected demand

Phase B
Historical CSV imports

Phase C
Statistical forecasting

Phase D
Reservation import

Phase E
Official POS / E2N / reservation integrations
```

The core preparation engine must work independently.

---

# 19. Voice Architecture

Later voice architecture:

```text
Speech-to-Text
        ↓
Intent Extraction
        ↓
Structured Validation
        ↓
Application Action
        ↓
Optional Text-to-Speech
```

Example voice command:

```text
"Wir haben noch fünf Kilo Bratkartoffeln."
```

Expected structured representation:

```json
{
  "intent": "update_preparation_stock",
  "preparation_product": "Bratkartoffeln",
  "quantity": 5,
  "unit": "kg"
}
```

Another example:

```json
{
  "intent": "get_next_preparation_task"
}
```

Use Pydantic validation.

Never execute arbitrary LLM-generated text directly.

---

# 20. Ingredient / Preparation Aliases

Kitchen staff may use different words.

Example:

```text
Bratkartoffeln
Bratkartoffel
Bratkart.
```

Support aliases.

Suggested fields:

```text
canonical_name_de
canonical_name_en
aliases[]
```

Unknown voice/search matches should require confirmation.

Do not automatically create new preparation products.

---

# 21. Food Waste Optimization

Later track:

```text
prepared quantity
sold quantity
remaining quantity
discarded quantity
```

Example:

```text
Prepared:
12 kg

Used:
8 kg

Waste:
4 kg
```

Future forecasts should balance:

```text
avoid shortage
vs
avoid over-preparation
```

---

# 22. Forecast Accuracy

Track forecast accuracy.

Potential metrics:

- MAE
- MAPE where appropriate
- absolute preparation error
- shortage rate
- over-preparation rate

Forecasts should eventually include uncertainty.

Example:

```text
Expected Schnitzel:
38 portions

Suggested range:
35–43
```

---

# 23. Success Metrics

Track:

- emergency preparation incidents
- forgotten preparation items
- stock-check duration
- service delays related to preparation
- food waste
- forecast error
- manual overrides
- shortage frequency
- over-preparation frequency

The project is successful if it reduces:

- emergency prep
- manual checking time
- forgotten items
- food waste

without increasing shortages.

---

# 24. Suggested Technology Stack

The developer has experience with Python, Flask/FastAPI, SQL, Pandas, data science, machine learning, and automation.

Recommended stack:

## Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- Alembic

## Database

Development:

- SQLite

Production:

- PostgreSQL

## Frontend

Recommended:

- React
- Next.js
- TypeScript

Alternative simpler MVP:

- FastAPI
- Jinja2
- HTMX
- Tailwind CSS

Prefer simplicity for the first version.

Do not introduce unnecessary microservices.

Use a modular monolith.

---

# 25. Suggested Project Structure

```text
restaurant-prep-system/
│
├── README.md
├── PROJECT_SPEC.md
├── .env.example
├── .gitignore
│
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   │
│   │   ├── api/
│   │   │   ├── ingredients.py
│   │   │   ├── preparation_products.py
│   │   │   ├── menu_items.py
│   │   │   ├── inventory.py
│   │   │   ├── preparation.py
│   │   │   ├── forecasts.py
│   │   │   └── voice.py
│   │   │
│   │   ├── models/
│   │   │   ├── menu_item.py
│   │   │   ├── preparation_product.py
│   │   │   ├── raw_ingredient.py
│   │   │   ├── preparation_task.py
│   │   │   └── ...
│   │   │
│   │   ├── schemas/
│   │   │
│   │   ├── repositories/
│   │   │
│   │   ├── services/
│   │   │   ├── inventory_service.py
│   │   │   ├── demand_service.py
│   │   │   ├── preparation_service.py
│   │   │   ├── priority_service.py
│   │   │   └── forecast_service.py
│   │   │
│   │   ├── integrations/
│   │   │   ├── base.py
│   │   │   ├── csv_provider.py
│   │   │   ├── manual_provider.py
│   │   │   ├── e2n_provider.py
│   │   │   └── resmio_provider.py
│   │   │
│   │   ├── voice/
│   │   │
│   │   ├── forecasting/
│   │   │
│   │   ├── core/
│   │   │
│   │   └── db/
│   │
│   ├── tests/
│   │
│   ├── requirements.txt
│   └── alembic/
│
├── frontend/
│
├── data/
│   ├── seed_menu_items.csv
│   ├── seed_preparation_products.csv
│   └── seed_raw_ingredients.csv
│
├── docs/
│   ├── architecture.md
│   ├── data-model.md
│   ├── preparation-engine.md
│   └── roadmap.md
│
└── scripts/
```

---

# 26. Service Layer

Business logic must not live directly in API routes.

Recommended services:

```text
InventoryService
RecipeService
DemandService
PreparationService
PriorityService
ForecastService
ReservationService
OrderHistoryService
VoiceCommandService
```

---

# 27. API Ideas

Potential routes:

```text
GET    /menu-items
POST   /menu-items

GET    /preparation-products
POST   /preparation-products

GET    /raw-ingredients
POST   /raw-ingredients

POST   /inventory/preparation/snapshot
POST   /inventory/raw/snapshot

POST   /demand/manual

POST   /preparation/calculate
GET    /preparation/today

POST   /preparation/tasks/{id}/start
POST   /preparation/tasks/{id}/complete

GET    /analytics/waste
GET    /analytics/forecast-accuracy
```

Do not blindly implement these routes.

Review them during architecture design.

---

# 28. Important Testing Cases

Create comprehensive tests.

Required scenarios:

- enough stock
- no stock
- partial stock
- safety stock
- unit conversions
- incompatible units
- multiple dishes using the same preparation product
- menu item without preparation mapping
- preparation product without recipe
- invalid negative quantities
- manual override
- duplicate preparation requirements
- priority ordering
- empty expected demand
- historical forecast unavailable
- reservation-adjusted demand
- preparation dependencies

Example:

```text
Dish A requires:
200 g Bratkartoffeln

Expected orders:
10

Required:
2 kg

Stock:
0.5 kg

Safety:
0.2 kg

Expected preparation:
1.7 kg
```

---

# 29. Data Integrity Rules

Important rules:

- quantities cannot be negative
- product names should be unique within logical scope
- units must be validated
- incompatible unit conversions must fail
- deleted products should preferably be soft-deleted
- historical task records should remain immutable where possible
- preparation calculations should be reproducible
- manual overrides should be logged

---

# 30. Audit and Observability

Record important actions:

- inventory updated
- demand entered
- forecast generated
- preparation task created
- task started
- task completed
- manual override
- waste recorded

Avoid logging unnecessary sensitive information.

---

# 31. UI Principles

This is a kitchen application.

It should not look like a complex ERP.

Requirements:

- tablet-first
- mobile-friendly
- large buttons
- large text
- high contrast
- minimal navigation
- minimal typing
- fast quantity entry
- category grouping
- clear priority
- clear readiness status

The most important question on the dashboard is:

> **What should I prepare next?**

---

# 32. Development Phases

## Phase 0 — Architecture

Before coding:

1. restate the business problem
2. define assumptions
3. identify unclear requirements
4. design architecture
5. design database schema
6. design API
7. design folder structure
8. create Mermaid diagrams
9. create milestone roadmap
10. list what should not be built yet

---

## Phase 1 — Core Data

Build:

- database connection
- migrations
- MenuItem
- PreparationProduct
- RawIngredient
- MenuItemPreparationRequirement
- StorageLocation
- Unit handling
- seed data

---

## Phase 2 — Manual Preparation Stock

Build:

- stock-check page
- preparation stock snapshot
- quantity update
- category grouping
- low-stock display

---

## Phase 3 — Demand Input

Build:

- manual expected order entry
- expected cover entry
- menu demand storage

---

## Phase 4 — Preparation Engine

Build:

```text
Expected Demand
    ↓
Menu Requirements
    ↓
Total Preparation Product Demand
    ↓
Current Stock
    ↓
Shortage
    ↓
Preparation Task
```

Add tests before UI complexity.

---

## Phase 5 — Priority Engine

Add explainable priority scoring.

Show:

- score
- level
- reasons

---

## Phase 6 — Kitchen Dashboard

Build:

- Critical
- High
- Normal
- Ready
- task start
- task completion
- quantity prepared
- manual override

---

## Phase 7 — Raw Ingredient Layer

Add:

- preparation recipes
- raw ingredients
- raw stock
- "Can we prepare this?" check

---

## Phase 8 — Historical Order Import

Support CSV first.

Add:

- historical order import
- weekday statistics
- dish popularity
- hourly analysis

---

## Phase 9 — Forecasting

Start with:

- weekday average
- moving average
- weighted average

Compare methods.

Do not use advanced ML until baseline quality is measured.

---

## Phase 10 — Reservations

Add:

- manual reservation count
- CSV import
- reservation-adjusted expected demand

---

## Phase 11 — Voice

Add:

- German speech-to-text
- English speech-to-text
- structured intents
- validation
- safe inventory updates

---

## Phase 12 — External Integrations

Investigate official integrations for:

- E2N
- POS
- Resmio
- reservation systems

Use adapters.

Do not couple core business logic to these systems.

---

## Phase 13 — Optimization

Use accumulated data for:

- forecast improvement
- waste reduction
- safety-stock tuning
- prep scheduling
- staffing insights
- restaurant-level analytics

---

# 33. Initial Seed Data

The handwritten lists provided for the project contain preparation products.

Because handwriting interpretation may be imperfect, seed data must always be editable.

Create:

```text
data/seed_preparation_products.csv
```

Suggested columns:

```text
name_de
name_en
category
unit
storage_location
minimum_stock
target_stock
prep_time_minutes
active
notes
```

Do not hardcode handwritten names into application logic.

---

# 34. Important Engineering Constraints

1. Do not build everything at once.
2. Do not introduce microservices initially.
3. Keep calculations deterministic.
4. AI should assist but not control core arithmetic.
5. Use strong validation.
6. Add tests before integrations.
7. Keep integrations behind interfaces.
8. Avoid overengineering.
9. Prefer readable code.
10. Explain architectural decisions.

---

# 35. AI Usage Rules

Appropriate AI uses:

- voice understanding
- multilingual commands
- name matching
- natural-language queries
- summaries
- assistant-style explanations

Do not use AI for:

- inventory arithmetic
- deterministic shortage calculation
- unit conversions
- silently changing quantities
- creating unknown ingredients automatically
- irreversible actions without validation

---

# 36. Long-Term Architecture

```text
Historical POS Orders
          +
Reservations
          +
Day / Time / Season
          +
Current Preparation Stock
          +
Menu Requirements
          ↓
Demand Forecast
          ↓
Preparation Requirement Engine
          ↓
Shortage Detection
          ↓
Priority Engine
          ↓
Kitchen Preparation Dashboard
          ↓
Worker Actions
          ↓
Actual Usage / Waste
          ↓
Forecast Improvement
```

---

# 37. Initial Codex Task

When using this file with Codex, begin with the following instruction:

```text
Read PROJECT_SPEC.md completely before writing code.

Do not start by generating the entire application.

First:

1. summarize the business problem
2. identify assumptions and unclear points
3. propose the MVP architecture
4. design the database schema
5. create a Mermaid architecture diagram
6. create a Mermaid ER diagram
7. propose the exact backend folder structure
8. define the first API endpoints
9. design the preparation calculation service
10. design the explainable priority algorithm
11. define test cases
12. create an implementation roadmap

Then stop and wait for approval before implementing Phase 1.

Important:
The handwritten kitchen items are Step-2 PREPARATION PRODUCTS, not raw ingredients.

The MVP priority is:
Menu Demand → Preparation Product Requirement → Current Prepared Stock → Shortage → Priority → Final Preparation List.

Keep the system simple, modular, testable, and suitable for a real restaurant kitchen.
```

---

# 38. Coding Style Expectations

When implementation begins:

- use type hints
- use Pydantic schemas
- use SQLAlchemy cleanly
- keep API routes thin
- place business logic in services
- create unit tests
- use clear naming
- avoid unnecessary abstractions
- document non-obvious logic
- create small commits / logical milestones
- avoid placeholder code where working code can be written
- never silently swallow errors

---

# 39. Definition of MVP Done

The MVP is considered complete when a worker can:

1. open the app
2. enter today's expected orders
3. enter current preparation stock
4. press calculate
5. see all required preparation products
6. see missing quantities
7. see priority order
8. understand why an item is high priority
9. mark a task in progress
10. mark a task completed
11. record final prepared quantity
12. repeat the process without editing source code

---

# 40. Final Product Vision

The long-term product should become:

> **An intelligent pre-service preparation planner for scratch-cooking restaurants.**

The system should allow a chef to know, before service:

- what is missing
- how much is missing
- what should be prepared first
- whether the kitchen can produce it
- whether current preparation is sufficient for expected demand
- where shortages are likely
- where over-preparation and waste can be reduced

The goal is not merely to digitize a paper checklist.

The goal is to make preparation planning faster, safer, more predictable, and increasingly data-driven.
