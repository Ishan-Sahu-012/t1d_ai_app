# T1D-AI Architecture Document

**Project:** AI-Powered Hypoglycemia Prediction and Carb-Counting Tool for Indian Type 1 Diabetes Diets

**Status:** Architecture specification (pre-implementation)

**Last updated:** 2026-08-18

---

## Executive Summary

T1D-AI is a mobile-first health tool that helps people with Type 1 Diabetes (T1D) manage two daily challenges: anticipating low blood glucose (hypoglycemia) and estimating carbohydrate intake from Indian meals. The system is deliberately scoped as a **decision-support tool**, not a medical device. It does not provide insulin dosing advice, does not claim clinical validation, and does not fabricate nutritional or model-performance data.

```
┌─────────────────────────────────────────────────────────────────┐
│                     Flutter Mobile App                          │
│              (Riverpod · Dio · GoRouter)                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS / JSON REST
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FastAPI Backend                             │
│         (Pydantic · SQLAlchemy · Auth · Business Logic)         │
└───────────────┬─────────────────────────────┬───────────────────┘
                │                             │
                ▼                             ▼
┌───────────────────────────┐   ┌─────────────────────────────────┐
│   SQLite (MVP)            │   │   Python ML Services            │
│   PostgreSQL-compatible   │   │   hypoglycemia · food_recognition│
│   schema design           │   │   (Pandas · sklearn · PyTorch)  │
└───────────────────────────┘   └─────────────────────────────────┘
```

---

## 1. Repository Structure

The repository is organized as a **monorepo** with clear boundaries between client, server, ML, data, and infrastructure. Current state: skeleton directories only; no application code yet.

```
t1d_ai_app/
│
├── mobile/                     # Flutter application (Dart)
│   ├── lib/
│   │   ├── app/                # App bootstrap, theme, router
│   │   ├── core/               # Shared utilities, constants, errors
│   │   ├── features/           # Feature modules (see §2)
│   │   └── shared/             # Reusable widgets, providers
│   ├── test/
│   └── pubspec.yaml
│
├── backend/                    # FastAPI application (Python)
│   ├── app/
│   │   ├── api/                # Route handlers (versioned)
│   │   ├── core/               # Config, security, dependencies
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── services/           # Business logic
│   │   ├── repositories/       # Data access layer
│   │   └── ml/                 # ML inference adapters (thin wrappers)
│   ├── alembic/                # Database migrations
│   ├── tests/
│   └── requirements.txt
│
├── ml/                         # Offline ML training & research code
│   ├── hypoglycemia/           # Time-series / tabular prediction
│   │   ├── training/
│   │   ├── evaluation/
│   │   └── inference/          # Standalone inference module (imported by backend)
│   └── food_recognition/       # Computer vision pipeline
│       ├── training/
│       ├── evaluation/
│       └── inference/          # OpenCV + PyTorch inference
│
├── data/
│   ├── raw/                    # Unprocessed inputs (gitignored; not committed)
│   └── processed/              # Cleaned, feature-ready data (gitignored)
│
├── models/                     # Trained artifact storage (gitignored)
│   ├── hypoglycemia/
│   └── food_recognition/
│
├── docs/                       # Architecture, API specs, ADRs
├── tests/                      # Cross-cutting integration / E2E tests
├── docker/                     # Dockerfiles, compose for local dev
│
├── .gitignore
└── README.md
```

### Directory Responsibilities

| Path | Owns | Does NOT own |
|------|------|--------------|
| `mobile/` | UI, local state, API client calls | Business logic, ML inference, DB access |
| `backend/` | Auth, validation, orchestration, persistence | Model training, heavy CV preprocessing |
| `ml/` | Training scripts, feature engineering, evaluation | HTTP routes, user sessions |
| `models/` | Serialized weights/checkpoints (local only) | Source code |
| `data/` | Datasets (local only, never invented) | Hardcoded sample medical data in code |
| `tests/` | End-to-end flows spanning mobile + API + ML | Unit tests (those live beside their modules) |

### Naming & Versioning Conventions

- API routes are versioned: `/api/v1/...`
- Database migrations managed by Alembic under `backend/alembic/`
- ML model artifacts versioned by filename convention: `{model_name}_v{semver}.pt`
- Environment config via `.env` files (never committed); `.env.example` documents required keys

---

## 2. Flutter Architecture

### Pattern: Feature-First + Clean Layers

Each feature is a self-contained module. Shared infrastructure lives in `core/` and `shared/`.

```
lib/
├── app/
│   ├── app.dart                # MaterialApp / CupertinoApp entry
│   ├── router.dart             # GoRouter route definitions
│   └── theme.dart
│
├── core/
│   ├── api/
│   │   ├── api_client.dart     # Dio singleton with interceptors
│   │   ├── api_endpoints.dart  # Path constants (synced with backend)
│   │   └── api_exceptions.dart
│   ├── config/
│   │   └── env.dart            # Base URL, timeouts (from --dart-define or .env)
│   └── utils/
│
├── features/
│   ├── auth/
│   │   ├── data/               # Repositories, DTOs, API calls
│   │   ├── domain/             # Entities, use-case interfaces
│   │   └── presentation/       # Screens, widgets, Riverpod providers
│   ├── glucose/
│   ├── hypoglycemia_alert/
│   ├── food_log/
│   ├── food_camera/
│   └── profile/
│
└── shared/
    ├── widgets/
    └── providers/              # Cross-feature providers (e.g. auth state)
```

### State Management: Riverpod

| Provider type | Use case |
|---------------|----------|
| `Provider` | Immutable services (ApiClient, repositories) |
| `FutureProvider` | One-shot async reads (user profile) |
| `AsyncNotifierProvider` | CRUD lists with refresh (glucose log, meal log) |
| `NotifierProvider` | Synchronous UI state (form fields, filters) |

**Rules:**
- API calls never originate from widgets directly; always through a repository.
- Providers expose `AsyncValue<T>` for loading/error/data states.
- Auth token managed by a dedicated `AuthNotifier`; Dio interceptor reads it.

### Navigation: GoRouter

- Declarative routes with redirect guards for unauthenticated users.
- Deep-link support for future notification taps (e.g. hypoglycemia alert).
- Shell route for bottom-navigation scaffold.

```
/                     → redirect to /home or /login
/login
/register
/home                   → dashboard (shell child)
/glucose                → glucose log & entry
/hypoglycemia           → risk overview & history
/food                   → meal log
/food/camera            → capture meal photo
/food/result/:id        → recognition result review
/profile
```

### HTTP Client: Dio

- Base options: JSON content type, configurable timeout, retry on network failure (not on 4xx).
- Interceptors: auth header injection, request/response logging (debug only), error normalization to `ApiException`.
- No mock/fake responses in production code paths.

### Key Flutter Principles

1. **DTO ↔ Domain mapping** at the repository boundary; UI never parses raw JSON.
2. **Offline-first consideration (future):** architecture leaves room for local caching (e.g. `drift` or `hive`) but MVP is online-only.
3. **Disclaimers in UI:** every prediction/estimation screen displays a non-dismissable informational banner stating the tool is not medical advice.

---

## 3. FastAPI Architecture

### Pattern: Layered (Router → Service → Repository → ORM)

```
backend/app/
├── main.py                     # FastAPI app factory, middleware, lifespan
├── api/
│   └── v1/
│       ├── router.py           # Aggregates sub-routers
│       ├── auth.py
│       ├── glucose.py
│       ├── hypoglycemia.py
│       ├── food.py
│       └── users.py
├── core/
│   ├── config.py               # Pydantic Settings (env vars)
│   ├── security.py             # JWT create/verify, password hashing
│   ├── dependencies.py         # get_db, get_current_user
│   └── exceptions.py           # HTTP exception handlers
├── models/                     # SQLAlchemy declarative models
├── schemas/                    # Pydantic v2 models (request/response)
├── services/
│   ├── glucose_service.py
│   ├── hypoglycemia_service.py
│   └── food_service.py
├── repositories/
│   ├── glucose_repository.py
│   └── ...
└── ml/
    ├── hypoglycemia_adapter.py # Loads model, runs inference
    └── food_adapter.py         # OpenCV preprocess + PyTorch inference
```

### Request Lifecycle

```
HTTP Request
  → Middleware (CORS, request ID)
  → Router (path matching)
  → Dependency injection (DB session, current user)
  → Pydantic schema validation (request body/query)
  → Service (business rules)
  → Repository (DB queries)  OR  ML Adapter (inference)
  → Pydantic schema serialization (response)
  → HTTP Response
```

### Configuration (Environment Variables)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | `sqlite:///./t1d_ai.db` (MVP) or `postgresql://...` |
| `SECRET_KEY` | JWT signing key |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Token TTL |
| `HYPO_MODEL_PATH` | Path to hypoglycemia model artifact |
| `FOOD_MODEL_PATH` | Path to food recognition model artifact |
| `ALLOWED_ORIGINS` | CORS origins for Flutter dev/prod |

### Cross-Cutting Concerns

- **Authentication:** JWT bearer tokens; refresh token flow (phase 2).
- **Authorization:** User can only access their own glucose/meal/prediction records.
- **Validation:** All inputs validated by Pydantic before reaching services.
- **Error responses:** Consistent shape (see §6).
- **Logging:** Structured JSON logs with request ID; no PII in logs.
- **File uploads:** Meal images via `multipart/form-data`; stored on local filesystem (MVP) or object storage (production).

### PostgreSQL Compatibility

- Use SQLAlchemy types that map cleanly to both SQLite and PostgreSQL (`String`, `DateTime(timezone=True)`, `Numeric`, `JSON`).
- Avoid SQLite-specific SQL in repositories; use ORM queries exclusively.
- Use Alembic for all schema changes; test migrations against both dialects before production cutover.
- SQLite limitations acknowledged: no concurrent writes; acceptable for single-user MVP/dev.

---

## 4. ML Architecture

ML code is split into **offline training** (`ml/`) and **online inference** (`backend/app/ml/` adapters that import from `ml/*/inference/`).

### 4.1 Hypoglycemia Prediction Module

**Location:** `ml/hypoglycemia/`

**Purpose:** Estimate the probability that a user will experience hypoglycemia within a configurable prediction horizon, based on recent glucose trends and contextual signals.

**Inputs (schema-level; values come from user/device, never hardcoded):**

| Feature | Source | Notes |
|---------|--------|-------|
| Recent glucose readings | User log / CGM import | Timestamped time series |
| Rate of change | Derived server-side | Computed from readings, not stored as medical fact |
| Time of day | Derived | Circadian context |
| Recent meal events | Meal log | Timing only; carbs from verified log entries |
| Activity level (optional) | User input | Enum, not inferred |

**Model candidates (to be selected during development with real data):**

| Approach | Library | When to use |
|----------|---------|-------------|
| Gradient boosting / RF on engineered features | scikit-learn | Tabular baseline, interpretable |
| Sequence model (LSTM/GRU) | PyTorch | If sufficient time-series data exists |
| Simple heuristic fallback | Pure Python | When model artifact is unavailable |

**Training pipeline:**

```
data/raw/  →  preprocessing  →  data/processed/
                                    ↓
                              feature engineering
                                    ↓
                              train / val / test split
                                    ↓
                              model training (ml/hypoglycemia/training/)
                                    ↓
                              evaluation (ml/hypoglycemia/evaluation/)
                                    ↓
                              export artifact → models/hypoglycemia/
```

**Evaluation requirements (when real data is available):**
- Report metrics on held-out data only (e.g. AUROC, sensitivity at fixed specificity).
- Never publish or display metrics until computed from actual evaluation runs.
- Document dataset provenance and limitations in `docs/`.

**Output:** A probability score (0.0–1.0) and a risk band (`low` | `moderate` | `high`). Thresholds are configurable server-side, not hardcoded medical constants.

### 4.2 Food Recognition Module

**Location:** `ml/food_recognition/`

**Purpose:** Identify Indian food items from a meal photograph and map recognized items to entries in a curated food database for carbohydrate estimation.

**Pipeline stages:**

```
Image (bytes)
  → OpenCV preprocessing (resize, normalize, optional augmentation at train time)
  → PyTorch model inference (classification or detection — TBD with data)
  → Top-K class predictions with confidence scores
  → Lookup in food database (backend DB, not hardcoded dict)
  → Return food item ID(s) + confidence; carbs retrieved from DB record
```

**Indian diet considerations (architectural, not data):**
- Food taxonomy organized by region/category (e.g. breads, rice dishes, snacks, sweets, beverages).
- Portion size is a separate user-editable field; the model identifies *what*, not *how much*.
- Multiple items per plate supported (multi-label or detection architecture TBD).
- Nutritional values stored in DB with `source` and `verified_at` fields for auditability.

**Constraints:**
- No invented nutritional values in code or docs.
- If a food item is not in the database, return `unknown` with prompt for manual entry.
- Confidence below configurable threshold → flag for user confirmation.

### 4.3 ML ↔ Backend Integration

```
backend/app/ml/hypoglycemia_adapter.py
  - Loads artifact from HYPO_MODEL_PATH at startup (lifespan event)
  - Exposes: predict(features: HypoFeatureVector) -> HypoPrediction
  - Graceful degradation if model file missing (return 503, not fake prediction)

backend/app/ml/food_adapter.py
  - Loads PyTorch model + label map from FOOD_MODEL_PATH
  - Exposes: recognize(image_bytes: bytes) -> list[FoodPrediction]
  - OpenCV preprocessing encapsulated here
```

### 4.4 Dependencies

```
# ml/ and backend/ shared ML requirements (pinned in requirements.txt)
pandas
numpy
scikit-learn
torch
opencv-python-headless
```

Training dependencies (jupyter, matplotlib, etc.) may live in a separate `requirements-dev.txt` to keep production images lean.

---

## 5. Database Schema

Designed for **SQLite (MVP)** with **PostgreSQL-compatible** types and constraints. All timestamps are UTC. All IDs are UUIDs (stored as `String(36)` in SQLite, `UUID` in PostgreSQL).

### Entity-Relationship Overview

```
users ─────────────┬──── glucose_readings
                   ├──── meal_events ──── meal_items ──── food_items
                   ├──── hypoglycemia_predictions
                   └──── food_recognition_results
```

### Tables

#### `users`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| email | String(255) | UNIQUE, NOT NULL |
| hashed_password | String(255) | NOT NULL |
| display_name | String(100) | |
| date_of_birth | Date | nullable |
| diagnosis_year | Integer | nullable |
| created_at | DateTime(tz) | NOT NULL, default now |
| updated_at | DateTime(tz) | NOT NULL |

#### `glucose_readings`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users.id, NOT NULL |
| value_mg_dl | Numeric(5,1) | NOT NULL |
| recorded_at | DateTime(tz) | NOT NULL |
| source | Enum(`manual`, `cgm`) | NOT NULL, default `manual` |
| notes | Text | nullable |
| created_at | DateTime(tz) | NOT NULL |

Index: `(user_id, recorded_at DESC)`

#### `food_items` (curated reference table)

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| name | String(200) | NOT NULL |
| name_local | String(200) | nullable (e.g. Hindi/Tamil name) |
| category | String(100) | NOT NULL |
| region | String(100) | nullable |
| carbs_per_serving_g | Numeric(6,2) | NOT NULL |
| serving_description | String(200) | NOT NULL (e.g. "1 medium piece") |
| serving_grams | Numeric(6,1) | nullable |
| source | String(200) | NOT NULL (citation of data origin) |
| verified_at | DateTime(tz) | nullable |
| is_active | Boolean | NOT NULL, default true |

> **Note:** Rows are populated from verified external sources only. No seed data with fabricated nutritional values will be committed to the repository.

#### `meal_events`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users.id, NOT NULL |
| meal_type | Enum(`breakfast`, `lunch`, `dinner`, `snack`) | NOT NULL |
| eaten_at | DateTime(tz) | NOT NULL |
| notes | Text | nullable |
| created_at | DateTime(tz) | NOT NULL |

#### `meal_items`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| meal_event_id | UUID | FK → meal_events.id, NOT NULL |
| food_item_id | UUID | FK → food_items.id, nullable (null if manual entry) |
| custom_name | String(200) | nullable (used when food_item_id is null) |
| portion_multiplier | Numeric(4,2) | NOT NULL, default 1.0 |
| carbs_override_g | Numeric(6,2) | nullable (user correction) |
| created_at | DateTime(tz) | NOT NULL |

Computed carbs: `COALESCE(carbs_override_g, food_items.carbs_per_serving_g * portion_multiplier)`

#### `food_recognition_results`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users.id, NOT NULL |
| image_path | String(500) | NOT NULL |
| status | Enum(`pending`, `completed`, `failed`) | NOT NULL |
| created_at | DateTime(tz) | NOT NULL |

#### `food_recognition_predictions`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| result_id | UUID | FK → food_recognition_results.id, NOT NULL |
| food_item_id | UUID | FK → food_items.id, nullable |
| label | String(200) | NOT NULL (raw model output label) |
| confidence | Numeric(5,4) | NOT NULL |
| rank | Integer | NOT NULL |

#### `hypoglycemia_predictions`

| Column | Type | Constraints |
|--------|------|-------------|
| id | UUID | PK |
| user_id | UUID | FK → users.id, NOT NULL |
| risk_score | Numeric(5,4) | NOT NULL (0.0–1.0) |
| risk_band | Enum(`low`, `moderate`, `high`) | NOT NULL |
| horizon_minutes | Integer | NOT NULL |
| model_version | String(50) | NOT NULL |
| feature_snapshot | JSON | NOT NULL (inputs used, for auditability) |
| created_at | DateTime(tz) | NOT NULL |

### Schema Design Principles

1. **No insulin fields** — the schema intentionally excludes insulin doses, IOB, or dosing recommendations.
2. **Auditability** — predictions store a feature snapshot and model version.
3. **User corrections** — `carbs_override_g` and `custom_name` allow manual override without discarding ML output.
4. **Soft reference data** — `food_items.is_active` allows deprecating entries without breaking historical logs.
5. **Portable SQL** — all DDL via Alembic; no dialect-specific features in MVP.

---

## 6. API Contracts

Base URL: `/api/v1`

All authenticated endpoints require header: `Authorization: Bearer <access_token>`

### Standard Error Response

```json
{
  "detail": "Human-readable error message",
  "error_code": "GLUCOSE_NOT_FOUND",
  "request_id": "uuid"
}
```

HTTP status codes: `400` validation, `401` unauthenticated, `403` forbidden, `404` not found, `422` Pydantic validation, `503` model unavailable.

---

### Auth

#### `POST /api/v1/auth/register`

Request:
```json
{
  "email": "user@example.com",
  "password": "string",
  "display_name": "string"
}
```

Response `201`:
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "display_name": "string"
}
```

#### `POST /api/v1/auth/login`

Request:
```json
{
  "email": "user@example.com",
  "password": "string"
}
```

Response `200`:
```json
{
  "access_token": "string",
  "token_type": "bearer",
  "expires_in": 3600
}
```

---

### Glucose

#### `POST /api/v1/glucose`

Request:
```json
{
  "value_mg_dl": 120.0,
  "recorded_at": "2026-08-18T10:30:00Z",
  "source": "manual",
  "notes": "optional"
}
```

Response `201`:
```json
{
  "id": "uuid",
  "value_mg_dl": 120.0,
  "recorded_at": "2026-08-18T10:30:00Z",
  "source": "manual",
  "notes": null,
  "created_at": "2026-08-18T10:31:00Z"
}
```

#### `GET /api/v1/glucose?from=ISO8601&to=ISO8601&limit=100`

Response `200`:
```json
{
  "items": [ { "...GlucoseReading" } ],
  "total": 42
}
```

---

### Hypoglycemia Prediction

#### `POST /api/v1/hypoglycemia/predict`

Triggers on-demand prediction using the user's recent data. No request body required (server gathers features).

Response `200`:
```json
{
  "id": "uuid",
  "risk_score": 0.0,
  "risk_band": "low",
  "horizon_minutes": 30,
  "model_version": "string",
  "created_at": "2026-08-18T10:31:00Z",
  "disclaimer": "This is a decision-support estimate, not medical advice. Not clinically validated."
}
```

Response `503` (model unavailable):
```json
{
  "detail": "Hypoglycemia prediction model is not loaded",
  "error_code": "MODEL_UNAVAILABLE"
}
```

#### `GET /api/v1/hypoglycemia/history?limit=20`

Response `200`:
```json
{
  "items": [ { "...HypoglycemiaPrediction" } ],
  "total": 5
}
```

---

### Food

#### `GET /api/v1/food/items?search=query&category=string&limit=20`

Search the curated food database.

Response `200`:
```json
{
  "items": [
    {
      "id": "uuid",
      "name": "string",
      "name_local": "string | null",
      "category": "string",
      "carbs_per_serving_g": 0.0,
      "serving_description": "string"
    }
  ],
  "total": 0
}
```

#### `POST /api/v1/food/recognize`

Request: `multipart/form-data` with field `image` (JPEG/PNG, max size TBD).

Response `202` (async processing) or `200` (sync MVP):
```json
{
  "id": "uuid",
  "status": "completed",
  "predictions": [
    {
      "food_item_id": "uuid | null",
      "label": "string",
      "confidence": 0.0,
      "rank": 1
    }
  ],
  "disclaimer": "Recognition results require user verification. Carb values from curated database."
}
```

#### `POST /api/v1/food/meals`

Request:
```json
{
  "meal_type": "lunch",
  "eaten_at": "2026-08-18T13:00:00Z",
  "items": [
    {
      "food_item_id": "uuid",
      "portion_multiplier": 1.5,
      "carbs_override_g": null
    }
  ],
  "notes": "optional"
}
```

Response `201`:
```json
{
  "id": "uuid",
  "meal_type": "lunch",
  "eaten_at": "2026-08-18T13:00:00Z",
  "total_carbs_g": 0.0,
  "items": [ { "...MealItem" } ],
  "created_at": "2026-08-18T13:01:00Z"
}
```

> `total_carbs_g` is computed server-side from verified food database values and user overrides. It is never a fabricated number.

---

### User Profile

#### `GET /api/v1/users/me`

#### `PATCH /api/v1/users/me`

Partial update of `display_name`, `date_of_birth`, `diagnosis_year`.

---

### Contract Synchronization

| Mechanism | Detail |
|-----------|--------|
| **Source of truth** | Pydantic schemas in `backend/app/schemas/` |
| **Flutter DTOs** | Hand-written Dart classes mirroring schemas (MVP); OpenAPI codegen considered for phase 2 |
| **Verification** | Contract tests in `tests/` compare OpenAPI spec against expected shapes |
| **Versioning** | Breaking changes require `/api/v2`; mobile sends `Accept-Version` header (phase 2) |

---

## 7. Communication Between Flutter and FastAPI

### Transport

| Aspect | Decision |
|--------|----------|
| Protocol | HTTPS (HTTP in local dev) |
| Format | JSON (`Content-Type: application/json`) |
| Image upload | `multipart/form-data` |
| Auth | JWT Bearer token in `Authorization` header |
| Date/time | ISO 8601 UTC strings |

### Dio Client Setup

```
BaseOptions
  baseUrl:   from env (e.g. http://10.0.2.2:8000 for Android emulator)
  connectTimeout: 10s
  receiveTimeout: 30s (longer for /food/recognize)

Interceptors
  1. AuthInterceptor      → attaches Bearer token
  2. ErrorInterceptor     → maps DioException to ApiException hierarchy
  3. LogInterceptor       → debug builds only
```

### Sequence: Authenticated API Call

```
Flutter Widget
  → Riverpod provider (notifier)
    → Repository.method()
      → ApiClient.get/post (Dio)
        → FastAPI Router
          → Pydantic validation
          → Service
          → Repository / ML Adapter
        ← JSON response
      ← DTO parsed to Domain entity
    ← AsyncValue updated
  ← Widget rebuilds
```

### Error Handling Matrix

| HTTP Status | Flutter handling |
|-------------|-----------------|
| 401 | Clear token, redirect to login |
| 403 | Show "access denied" snackbar |
| 422 | Display field-level validation errors |
| 503 | Show "service temporarily unavailable" (model not loaded) |
| Network error | Show offline message, offer retry |

### Security

- Tokens stored in `flutter_secure_storage` (not SharedPreferences).
- Certificate pinning considered for production (phase 2).
- No secrets in Dart source; base URL and feature flags via `--dart-define` or env config.
- CORS restricted to known origins on the backend.

---

## 8. Model Inference Flow

### Hypoglycemia Prediction (On-Demand)

```
┌──────────┐    POST /hypoglycemia/predict    ┌──────────────┐
│  Flutter  │ ──────────────────────────────► │   FastAPI    │
│  App      │                                  │   Router     │
└──────────┘                                  └──────┬───────┘
                                                       │
                                                       ▼
                                              ┌─────────────────┐
                                              │ Hypoglycemia    │
                                              │ Service         │
                                              └──────┬──────────┘
                                                     │
                                    ┌────────────────┼────────────────┐
                                    ▼                ▼                ▼
                           ┌──────────────┐  ┌─────────────┐  ┌──────────────┐
                           │ Glucose      │  │ Meal        │  │ Feature      │
                           │ Repository   │  │ Repository  │  │ Engineering  │
                           │ (last N hrs) │  │ (last N hrs)│  │ (pandas)     │
                           └──────────────┘  └─────────────┘  └──────┬───────┘
                                                                      │
                                                                      ▼
                                                             ┌─────────────────┐
                                                             │ Hypoglycemia    │
                                                             │ ML Adapter      │
                                                             │ (sklearn/torch) │
                                                             └────────┬────────┘
                                                                      │
                                                                      ▼
                                                             ┌─────────────────┐
                                                             │ Map score →     │
                                                             │ risk_band       │
                                                             │ Store prediction│
                                                             │ Return response │
                                                             └─────────────────┘
```

**Steps:**

1. Flutter sends `POST /api/v1/hypoglycemia/predict` (authenticated).
2. Service fetches user's glucose readings and recent meals from DB.
3. Feature engineering computes derived signals (rate of change, time since last meal, etc.).
4. If insufficient data (e.g. fewer than N readings), return `400` with `error_code: INSUFFICIENT_DATA` — never extrapolate or fabricate readings.
5. ML adapter loads model (cached at startup) and returns probability.
6. Service maps probability to `risk_band` using configurable thresholds.
7. Prediction persisted to `hypoglycemia_predictions` with feature snapshot.
8. Response returned with mandatory disclaimer field.

**Failure modes:**

| Condition | Behavior |
|-----------|----------|
| Model file missing | `503 MODEL_UNAVAILABLE` |
| Insufficient glucose data | `400 INSUFFICIENT_DATA` |
| Feature computation error | `500` with logged details, generic message to client |

---

## 9. Food Recognition Flow

```
┌──────────┐  POST /food/recognize (multipart)  ┌──────────────┐
│  Flutter  │ ─────────────────────────────────►│   FastAPI    │
│  Camera   │                                    │   Router     │
└──────────┘                                     └──────┬───────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │ Food Service    │
                                               └──────┬──────────┘
                                                      │
                              ┌────────────────────────┼────────────────────┐
                              ▼                        ▼                    ▼
                     ┌──────────────┐        ┌──────────────┐    ┌──────────────────┐
                     │ Save image   │        │ Food ML      │    │ Food Items       │
                     │ to storage   │        │ Adapter      │    │ Repository       │
                     └──────────────┘        │ (OpenCV +    │    │ (match label →   │
                                             │  PyTorch)    │    │  DB record)      │
                                             └──────┬───────┘    └────────┬─────────┘
                                                    │                       │
                                                    ▼                       │
                                           ┌─────────────────┐              │
                                           │ Raw predictions │──────────────┘
                                           │ (label, conf)   │
                                           └────────┬────────┘
                                                    │
                                                    ▼
                                           ┌─────────────────┐
                                           │ Store result +  │
                                           │ predictions in  │
                                           │ DB              │
                                           └────────┬────────┘
                                                    │
                                                    ▼
                                           ┌─────────────────┐
                                           │ Return top-K    │
                                           │ predictions to  │
                                           │ Flutter         │
                                           └─────────────────┘
```

**Flutter-side flow after recognition:**

```
1. User captures photo → preview screen
2. Upload to POST /food/recognize
3. Display predictions ranked by confidence
4. User confirms / corrects items and portion sizes
5. User submits confirmed meal via POST /food/meals
```

**Key rules:**

- Model output is a **suggestion**; the user must confirm before logging.
- If `confidence < CONFIDENCE_THRESHOLD` (env var), UI highlights uncertainty.
- If no DB match for a label, `food_item_id` is `null`; user must search manually or enter custom item.
- Carb values displayed only after resolving to a `food_items` record or a user-provided override.
- No insulin-related calculations anywhere in this flow.

---

## 10. Testing Strategy

### Testing Pyramid

```
          ┌─────────┐
          │  E2E    │  few, high-value flows
          ├─────────┤
          │ Integr. │  API + DB + ML adapter
          ├─────────┤
          │  Unit   │  many, fast, isolated
          └─────────┘
```

### Backend (`backend/tests/`)

| Layer | Tool | What to test |
|-------|------|-------------|
| Unit | pytest | Services (mocked repos), feature engineering, risk band mapping |
| Unit | pytest | Pydantic schema validation edge cases |
| Integration | pytest + TestClient | API routes with in-memory SQLite |
| Integration | pytest | Repository CRUD against test DB |
| ML | pytest | Inference adapter with fixture model (tiny synthetic weights, not fake accuracy claims) |
| Contract | pytest + schemathesis (phase 2) | OpenAPI spec conformance |

**Important:** ML tests verify that the pipeline runs end-to-end (input shape → output shape, no exceptions). Performance/accuracy tests run only when real labeled data is available in `data/` (not committed).

### Flutter (`mobile/test/`)

| Layer | Tool | What to test |
|-------|------|-------------|
| Unit | flutter_test | Repository mapping (JSON → entity), utility functions |
| Unit | flutter_test | Riverpod provider state transitions |
| Widget | flutter_test | Key screens render loading/error/data states |
| Integration | integration_test | Login → log glucose → view prediction (against local backend) |

### Cross-Cutting (`tests/`)

| Test | Description |
|------|-------------|
| API contract test | Verify every endpoint in §6 returns expected schema shape |
| Migration test | Alembic upgrade/downgrade on clean DB |
| Docker smoke test | `docker compose up` → health check passes |

### CI Pipeline (Future)

```
on push / PR:
  1. backend:  ruff lint → pytest → coverage report
  2. mobile:   flutter analyze → flutter test
  3. ml:       pytest ml/ (training pipeline smoke, not accuracy)
  4. secrets:  trufflehog / gitleaks scan
```

### What We Do NOT Test

- Medical accuracy of predictions (requires clinical study design, out of scope).
- Nutritional correctness (verified separately against source databases).
- Insulin dosing (feature does not exist).

---

## Appendix A: Non-Functional Requirements

| Requirement | Target (MVP) |
|-------------|-------------|
| API response time (non-ML) | < 200 ms p95 |
| Food recognition inference | < 5 s p95 (sync MVP) |
| Hypoglycemia prediction | < 1 s p95 |
| Mobile app cold start | < 3 s |
| Uptime | Best effort (single-instance MVP) |

## Appendix B: Out of Scope (Explicit)

- Insulin dose calculation or IOB tracking
- CGM device integration (architecture allows `source: cgm` but no device SDK in MVP)
- Clinical validation or regulatory submission
- Fabricated datasets, nutritional data, or model metrics
- Real-time push notifications (phase 2)

## Appendix C: Implementation Order (Recommended)

1. Backend skeleton: auth, user, glucose CRUD, DB migrations
2. Flutter skeleton: login, glucose log, GoRouter + Riverpod + Dio
3. Food database ingestion pipeline (from verified sources only)
4. Food search + manual meal logging (no ML yet)
5. ML training pipeline scaffolding (no fake data)
6. Food recognition inference integration
7. Hypoglycemia feature engineering + model training
8. Hypoglycemia prediction endpoint + Flutter UI
9. Integration tests + Docker compose for local dev

---

*This document is the authoritative architecture reference. Implementation must not deviate without updating this document first.*
