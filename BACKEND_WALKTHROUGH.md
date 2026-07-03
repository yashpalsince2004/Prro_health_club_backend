# Prro Health Club ERP - Backend Architecture Walkthrough

This document provides a comprehensive technical overview of the backend architecture developed for the **Prro Health Club ERP** (Gym Management System).

---

## Table of Contents
1. [Project Overview & Technology Stack](#1-project-overview--technology-stack)
2. [Directory Structure](#2-directory-structure)
3. [Component Architecture & Detailed Implementation](#3-component-architecture--detailed-implementation)
   - [Core & Configuration](#core--configuration)
   - [Database & Migrations](#database--migrations)
   - [Security & Authentication](#security--authentication)
   - [Middlewares & Utilities](#middlewares--utilities)
   - [API Routing & Endpoints](#api-routing--endpoints)
4. [Verification & Testing](#4-verification--testing)
5. [Recent Fixes & Bug Resolutions](#5-recent-fixes--bug-resolutions)

---

## 1. Project Overview & Technology Stack

The backend is built from the ground up to support a commercial-grade, multi-branch SaaS Gym Management ERP system. It handles:
- Core staff roles (Administrators, Receptionists, Trainers, and Members).
- Dynamic memberships, payments, attendance, and biometric sync.
- Flexible multi-tenant expansion and role-based API security.

### Core Tech Stack:
- **Language:** Python 3.12+ (tested and compatible with Python 3.14)
- **Framework:** FastAPI
- **Database ORM:** SQLAlchemy 2.0 (configured with SQLite batch support for local dev, ready for Supabase PostgreSQL)
- **Migrations:** Alembic
- **Validation:** Pydantic v2
- **Logging:** Loguru (structured logging with JSON & console formatters)
- **Authentication:** JWT (via `PyJWT`) and native `bcrypt` password hashing

---

## 2. Directory Structure

Below is the directory tree of the current repository layout:

```text
backend/
├── .env                  # Local environment file (ignored in git)
├── .env.example          # Sample environment template
├── .gitignore            # Git exclusion settings
├── alembic.ini           # Alembic database migration config
├── alembic/              # Alembic database migrations environment
│   └── env.py            # Migration runtime setup
└── app/                  # Application core package
    ├── api/              # API Route Handlers
    │   └── v1/           # Version 1 Router & Endpoints
    │       ├── auth/     # Auth endpoint module
    │       ├── health.py # System Health endpoints
    │       └── router.py # Router aggregator
    ├── core/             # Configuration, Logging, Security
    │   ├── config.py     # Pydantic Settings manager
    │   ├── constants.py  # Shared global constants
    │   ├── exceptions.py # Unified Exception mappings
    │   ├── logging.py    # Loguru configuration
    │   └── security.py   # Bcrypt and JWT utilities
    ├── database/         # Database Sessions & Metadata
    │   ├── base.py       # Metadata registry for Alembic
    │   ├── database.py   # DB setup helper
    │   ├── mixins.py     # SQLAlchemy 2.0 mixins
    │   └── session.py    # Database Session engine generator
    ├── dependencies/     # Dependency injection library
    │   └── auth.py       # Auth context parser & RBAC filters
    ├── middleware/       # Custom ASGI Middleware
    │   └── request_context.py # Traceability middleware
    ├── utils/            # Shared utilities
    │   └── response.py   # Standardized JSON response helpers
    └── main.py           # Application bootstrapper
```

---

## 3. Component Architecture & Detailed Implementation

### Core & Configuration

*   **[app/core/config.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/core/config.py):**
    Manages runtime settings dynamically using `pydantic-settings`. Reads properties like `SECRET_KEY`, `DATABASE_URL`, `ENVIRONMENT`, `DEBUG`, `CORS_ORIGINS`, timezone constraints (`Asia/Kolkata`), and Supabase connection settings.
*   **[app/core/constants.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/core/constants.py):**
    Hosts domain-wide enum types (e.g. roles: `admin`, `trainer`, `receptionist`, `member`) and session configuration constraints.
*   **[app/core/logging.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/core/logging.py):**
    Configures `Loguru` to capture logs from multiple logging libraries. Intercepts standard library handlers and prints clean, structured output with trace IDs.
*   **[app/core/exceptions.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/core/exceptions.py):**
    Provides a base `APIException` extending HTTP parameters, with specialized subclasses for databases, validation, authentication, and permission limits.

### Database & Migrations

*   **[app/database/session.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/database/session.py):**
    Creates the SQLAlchemy Database Engine. If SQLite is in use (e.g. during local tests), it applies custom threading optimizations. Yields sessions safely using a `get_db` generator.
*   **[app/database/mixins.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/database/mixins.py):**
    Establishes code reusability using SQLAlchemy 2.0 mixin classes:
    - `UUIDPrimaryKeyMixin`: Automatically generates UUIDv4 keys.
    - `AuditMixin`: Records audit logs (`created_at`, `updated_at`, `created_by`, `updated_by`).
    - `SoftDeleteMixin`: Standard soft-delete queries using `is_deleted` and `deleted_at`.
    - `TenantMixin`: Automatically structures multi-tenant scoping via `tenant_id`.
*   **[alembic/env.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/alembic/env.py):**
    Modified to run migrations dynamically using credentials fetched directly from Pydantic Settings. Added `render_as_batch=True` to bypass SQLite's constraint modification limits.

### Security & Authentication

*   **[app/core/security.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/core/security.py):**
    Exposes hashing algorithms using native `bcrypt` (bypassing legacy `passlib` versions, ensuring smooth compilation on newer environments like Python 3.14). Signs access tokens and refresh tokens using HMAC-SHA256 via `PyJWT`.
*   **[app/dependencies/auth.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/dependencies/auth.py):**
    Provides dependency injections to protect route handlers:
    - `get_current_user_context`: Resolves HTTP Bearer JWTs, decodes claims, and outputs a validated `UserContext`.
    - `RoleChecker`: Provides RBAC (Role-Based Access Control) filters to reject unauthorized roles (e.g., restricting trainer dashboards from members).

### Middlewares & Utilities

*   **[app/middleware/request_context.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/middleware/request_context.py):**
    Tracks user operations. Assigns a unique `request_id` to every request lifecycle. Attaches it to the contextual logging thread and returns it in the response header (`X-Request-ID`).
*   **[app/utils/response.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/utils/response.py):**
    Standardizes client responses. Implements unified responders:
    - `success_response(...)` (returns a `{ "success": true, "message": ..., "data": ... }` envelope)
    - `error_response(...)` (returns a `{ "success": false, "error": { "code": ..., "message": ..., "details": ... } }` envelope)

### API Routing & Endpoints

*   **[app/main.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/main.py):**
    Hooks up custom middlewares (GZip, CORS, Host check, request traceability) and attaches custom error handlers. Mounts routers globally under `/api/v1`.
*   **[app/api/v1/router.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/api/v1/router.py):**
    Merges all sub-routes into one aggregated `api_router`.
*   **[app/api/v1/health.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/api/v1/health.py):**
    System monitoring endpoints: `/health` (ping), `/version` (metadata check), and `/ready` (active database & Supabase check).
*   **[app/api/v1/auth/endpoints.py](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/app/api/v1/auth/endpoints.py):**
    Controls user session operations: `/login`, `/refresh`, `/logout`, `/forgot-password`, `/reset-password`, `/me` (identity check), and `/admin-only` (RBAC test).

---

## 4. Verification & Testing

The login flow, tokens exchange, database failover configurations, and role limits have been thoroughly validated.

### 1. Verification of Login and Token Retrieval
```bash
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"email": "admin@prrohealthclub.com", "password": "Password123"}' \
  http://localhost:8000/api/v1/auth/login
```
Response:
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1...",
    "refresh_token": "eyJhbGciOiJIUzI1...",
    "token_type": "bearer",
    "expires_in": 1800
  },
  "meta": {}
}
```

### 2. Verification of RBAC Rules
An endpoint tagged with `RoleChecker(allowed_roles=["admin"])` was requested using a Trainer account JWT:
```bash
curl -s -H "Authorization: Bearer <trainer_access_token>" \
  http://localhost:8000/api/v1/auth/admin-only
```
Response (403 Forbidden):
```json
{
  "success": false,
  "error": {
    "code": "FORBIDDEN",
    "message": "Access denied: Role 'trainer' is not authorized",
    "details": {}
  },
  "request_id": "ed854355-168f-4075-818c-c8a3d4ec7c19",
  "timestamp": "2026-07-02T13:38:02.928630+00:00"
}
```

---

## 5. Recent Fixes & Bug Resolutions

1.  **Repository Cleanliness (.gitignore):**
    Created a standard [gitignore](file:///Users/yashpal/Documents/Vibe_Project/Pro_health_club/backend/.gitignore) file containing:
    - `.env`, `.env.*`
    - `__pycache__/`
    - `*.pyc`
    - `venv/`
2.  **Config Variable Synchronization (`ENVIRONMENT`):**
    Aligned references to the app environment. Renaming the setting parameter to `ENVIRONMENT` caused startup crashes where `settings.ENV` was still accessed. Updated all occurrences in `main.py` and `health.py` to use `settings.ENVIRONMENT`.
3.  **FastAPI Router Mounting Error:**
    Fixed the API discovery bug. The app had mounted `api_router` using `app.mount("/api/v1", api_router)`. In FastAPI, `APIRouter` objects must be registered via `app.include_router(api_router, prefix="/api/v1")`. The mount logic was corrected, immediately fixing Swagger `/docs` route rendering and exposing all health and security endpoints.
