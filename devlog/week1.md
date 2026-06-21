# Week 1 — Docker Infrastructure & FastAPI Foundation

**Project:** arXiv Research Paper Curator
**Date:** June 2026
**Goal:** Get all 6 microservices running, connected, and verified with a live health endpoint.

---

## What I Built

A complete containerized infrastructure from scratch — 6 services orchestrated via Docker Compose, a typed configuration layer, a SQLAlchemy ORM model, a FastAPI application with lifecycle management, database connection pooling, and a build automation layer via Makefile.

**Verification target:** `make health` → `{"status": "ok", "checks": {"postgres": "healthy"}}`

---

## Architecture: Microservices on Docker

This project uses a **microservices architecture** — the same pattern used by Netflix (1,000+ services), Amazon, and Uber. Instead of one giant application that does everything, each concern is split into a small, focused service with a single responsibility.

| Service | Image | Role | Port |
|---------|-------|------|------|
| FastAPI | Custom (Dockerfile) | API server — handles all HTTP requests | 8000 |
| PostgreSQL | `postgres:16` | Relational store — paper metadata | 5432 |
| OpenSearch | `opensearchproject/opensearch:2.19.0` | Search engine — keyword + vector search | 9200 |
| Airflow | `apache/airflow:3.0.0` | Scheduler — daily ingestion pipeline | 8080 |
| Ollama | `ollama/ollama:latest` | Local LLM server — runs models on-device | 11434 |
| OpenSearch Dashboards | `opensearchproject/opensearch-dashboards:2.19.0` | Visual search UI | 5601 |

**Why microservices?** Each service fails, scales, and deploys independently. If FastAPI crashes, PostgreSQL keeps running and no data is lost. If OpenSearch needs more memory, only that container is scaled — the rest of the stack is untouched. This is the foundational architectural choice that makes the entire system production-grade.

---

## Dockerfile — Containerizing the FastAPI App

The Dockerfile only describes the FastAPI service. PostgreSQL, OpenSearch, Airflow, and Ollama use pre-built official images that need no custom Dockerfile — they are pulled directly from Docker Hub.

The most important design decision in the Dockerfile is **layer caching optimization**. Docker builds images in sequential layers and caches each one. The key insight is that Python dependencies (which take several minutes to install) almost never change — but source code changes dozens of times a day. By copying only the dependency manifest files first and installing dependencies before copying the application code, Docker caches the heavy dependency installation layer. Every subsequent build triggered by a code change skips dependency installation entirely and finishes in seconds instead of minutes. This single ordering decision saves 5–10 minutes on every iterative build during development.

The base image is `python:3.13-slim` rather than the full `python:3.13`. The `slim` variant removes documentation, locales, and development tools that are never needed at runtime — producing an image roughly 3× smaller, with fewer installed packages and therefore a smaller attack surface for security vulnerabilities.

All dependency installation uses `uv sync --frozen`. The `--frozen` flag refuses to update the lockfile and installs exact pinned versions from `uv.lock`. This guarantees that the container built on a developer's MacBook and the container built on a CI server six months later install identical library versions — no surprise behavioral changes from upstream upgrades.

---

## compose.yml — Orchestrating All 6 Services

`compose.yml` is the master control file for the entire stack. It defines how each service starts, what environment variables it receives, how data is stored, how services discover each other, and the order in which they must start.

### How Containers Talk to Each Other

Docker automatically creates a private internal network for every service listed in `compose.yml`. Services address each other using their **container name as a hostname** — not `localhost`. Inside a container, `localhost` refers to that container itself, not to any other service. So when FastAPI needs to connect to PostgreSQL, it uses the hostname `postgres` (the container name), which Docker resolves to the correct internal IP address automatically. This is why the `.env` file changed from `POSTGRES_HOST=localhost` (correct for local development) to `POSTGRES_HOST=postgres` (correct when running inside Docker).

### Volumes — Why Data Survives Container Restarts

By default, a Docker container is stateless. When it stops, every file written inside it is gone permanently. For a database, this would mean losing all papers every time the stack restarts — completely unacceptable.

Named volumes solve this. Each persistent service (PostgreSQL, OpenSearch, Ollama) mounts a named volume that lives on the host machine, outside of any container. The container stops, the volume stays. The container is deleted and recreated, the volume is still there. All papers, all search indices, all downloaded LLM models survive restarts, upgrades, and crashes.

### Healthchecks — Container Start ≠ Service Ready

A critical mistake beginners make: assuming a container being "started" means the service inside is ready to accept connections. PostgreSQL container starts in milliseconds, but the PostgreSQL database engine takes 10–15 seconds to initialize before it can handle queries. OpenSearch takes even longer.

Healthchecks solve this by periodically running a lightweight probe against each service. PostgreSQL uses `pg_isready` — a built-in utility that returns success only when the database engine is accepting connections. OpenSearch uses an HTTP request to its cluster health endpoint. Docker marks a service `healthy` only after the probe succeeds consistently.

### `depends_on` with `service_healthy` — Controlling Startup Order

FastAPI is configured to wait for both PostgreSQL and OpenSearch to be `healthy` before it starts. Without this, FastAPI would launch immediately, attempt to connect to a database that isn't ready, and crash. With `depends_on: condition: service_healthy`, Docker holds FastAPI back until both services have passed their healthchecks — eliminating the entire class of race-condition startup failures.

### Hot Reload During Development

The `develop.watch` section in FastAPI's config watches the local `src/` folder and automatically syncs any file change into the running container. Edit a route handler on the Mac, save the file, and the running FastAPI process picks up the change in under a second — no Docker restart required. This makes the development feedback loop nearly as fast as running the app locally.

### Airflow 3.0 — A Breaking Change

Airflow 3.0 changed its startup behavior compared to earlier versions. Without explicitly setting `command: standalone`, the Airflow container starts and immediately exits because it doesn't know which component to run. The `standalone` command launches the scheduler, API server, and database initialization all in one process — the correct mode for local development.

### Environment Variable Injection

Containers cannot read the `.env` file directly. Values must be explicitly passed into each container via the `environment` section in `compose.yml`. The `${VARIABLE_NAME}` syntax tells Docker Compose to read the value from the `.env` file on the host and inject it into the container as an environment variable. This keeps secrets out of the `compose.yml` file itself — secrets stay in `.env` which is gitignored.

---

## src/config.py — Typed, Validated Configuration

The configuration layer uses **Pydantic Settings** instead of the common pattern of calling `os.getenv()` scattered across different files.

`os.getenv()` has two critical problems. First, it always returns a string — so `os.getenv('POSTGRES_PORT')` returns the string `"5432"`, not the integer `5432`. Every caller has to remember to cast it. Second, if a variable is missing from `.env`, it silently returns `None` — the application continues running and only crashes much later with a confusing error unrelated to the actual root cause.

Pydantic Settings solves both problems. Fields declared without a default value are **required** — if they are absent from `.env`, the application crashes immediately on startup with a clear, specific error message naming exactly which variable is missing. Fields are automatically cast to their declared Python type — an `int` field gets an integer, a `str` field gets a string. One settings object is created once and imported everywhere — no scattered `os.getenv()` calls.

This embodies the **fail-fast principle**: surface configuration errors at startup with clear messages rather than letting them propagate into cryptic runtime failures 30 minutes later during the first real database query.

---

## src/models/paper.py — SQLAlchemy ORM

An ORM (Object-Relational Mapper) lets you write Python objects instead of raw SQL. Instead of writing `INSERT INTO papers (title, abstract) VALUES (...)` with string concatenation (which opens SQL injection vulnerabilities), you create a `Paper` object with attributes and let SQLAlchemy generate the correct SQL.

**Why the arXiv paper ID as the primary key?** Every paper on arXiv has a globally unique identifier like `2301.07041`. Using it as the primary key means the database itself enforces deduplication — inserting the same paper twice fails gracefully on a primary key conflict rather than creating a duplicate row. It also makes URLs meaningful: `/api/v1/papers/2301.07041` is self-documenting in a way that `/api/v1/papers/42` is not.

**`created_at` and `updated_at` with server defaults:** These timestamps are set and maintained by the database engine, not by application code. This means they are accurate even if data is inserted from multiple sources (the API, a migration script, the Airflow pipeline). The database is the single source of truth for when records were created and modified.

**Storing authors as a JSON string in a Text column:** A paper has multiple authors. Rather than creating a separate `authors` table with a foreign key relationship (premature complexity for Phase 1), authors are serialized to a JSON string and stored in a Text column. The application layer serializes when saving and deserializes when reading. This will be revisited if querying by author becomes a core feature.

---

## src/services/database.py — Connection Pool Management

The database layer has three distinct components with different lifecycles:

**The Engine** is created once when the application starts and lives for the entire application lifetime. It manages a pool of pre-opened connections to PostgreSQL so that each incoming request doesn't pay the cost of establishing a new TCP connection from scratch. The pool reuses connections across requests.

**`pool_pre_ping=True`** tells the engine to test each connection with a lightweight probe before handing it to a request. If PostgreSQL was restarted and the connection in the pool is now stale (the TCP socket is broken), the engine detects this, discards the dead connection, and opens a fresh one — transparently, without the request ever seeing an error. This makes the application resilient to database restarts without requiring any manual intervention or service restart.

**The `get_db()` generator function** provides a fresh database session to each incoming request. The critical design here is using `yield` instead of `return`. When a route function requests a database session, `get_db()` creates one, yields it to the route function, and pauses. The route function runs to completion. Then `get_db()` resumes and hits the `finally` block which closes the session — **regardless of whether the route succeeded or raised an exception**. This makes connection leaks structurally impossible. A `return`-based approach would require every route function to remember to close the session manually — a guarantee that breaks the moment someone writes an early return or an exception propagates.

**`autocommit=False` and `autoflush=False`** mean changes are never sent to the database until the application explicitly commits. This gives the application full control over transaction boundaries — if something goes wrong partway through a multi-step operation, a rollback undoes all changes atomically. Data either fully commits or fully rolls back; there is no in-between state where only some changes reach the database.

---

## src/main.py — FastAPI Application Entry Point

FastAPI's `lifespan` context manager replaces the older `@app.on_event("startup")` pattern. Code before the `yield` runs exactly once when the application starts — used here to call `create_tables()` which issues `CREATE TABLE IF NOT EXISTS` for all SQLAlchemy models. Code after the `yield` runs once when the application shuts down gracefully. In future phases this is where database connections will be closed, background tasks cancelled, and caches flushed.

**API versioning with the `/api/v1` prefix** is applied to all routers at registration time. When the API needs to introduce breaking changes in the future, a `/api/v2` prefix can be added alongside the existing one. Both versions serve requests simultaneously, and existing clients pointing at `/api/v1` never break. This is the standard pattern used by every public API that needs to evolve without forcing all clients to upgrade at once.

---

## src/routers/health.py — Production Health Endpoint

Every production system has a health endpoint. Load balancers query it to decide whether to route traffic to an instance. Monitoring systems alert when it returns `unhealthy`. Docker's `healthcheck` can call it to determine if the application container itself is ready.

The health check runs `SELECT 1` against PostgreSQL — the simplest possible SQL query. It touches no tables, performs no work, and returns the number 1 in under 1ms. Its only purpose is to prove the TCP connection to the database is alive.

The entire database check is wrapped in a `try/except`. This is intentional. If PostgreSQL is down, the health endpoint must **not** crash — it must return a structured response describing what is unhealthy and why. Without the `try/except`, a downed database propagates an exception through the health endpoint itself, returning a 500 error that tells the monitoring system nothing useful. With it, the endpoint always returns 200 with `{"postgres": "unhealthy: connection refused"}` — actionable diagnostic information.

---

## Makefile — Build Automation

The Makefile wraps long Docker Compose commands into short, memorable aliases. The entire stack is operable without memorizing a single flag or port number.

| Command | What It Does |
|---------|-------------|
| `make start` | Build FastAPI image (if changed) and start all 6 services in background |
| `make stop` | Stop all services gracefully |
| `make restart` | Stop then start — used after changing `compose.yml` or `Dockerfile` |
| `make status` | List all containers with their current health status and port mappings |
| `make logs` | Stream live logs from all services simultaneously |
| `make health` | Call the health endpoint and pretty-print the JSON response |
| `make format` | Auto-fix all code formatting issues with Ruff |
| `make lint` | Check code quality (Ruff) and type correctness (mypy) |
| `make test` | Run the full test suite with verbose output |
| `make clean` | **Danger:** Stop everything and permanently delete all data volumes |

---

## Complete Startup Flow

Running `make start` triggers a carefully ordered startup sequence. Docker reads `compose.yml`, identifies which services depend on which, and orchestrates the entire boot process automatically. The diagram below shows the exact sequence and what happens at each step:

```
make start
    │
    ├── postgres     → pulls image → starts → healthcheck: pg_isready (every 10s)
    │                                          after ~15s → status: healthy
    │
    ├── opensearch   → pulls image → starts → healthcheck: curl /_cluster/health (every 30s)
    │                                          after ~35s → status: healthy
    │
    ├── airflow      → waits for postgres healthy
    │                → command: standalone → scheduler + api-server + db-init
    │
    ├── ollama       → starts LLM server, ready to serve models
    │
    ├── opensearch-dashboards → waits for opensearch healthy → starts UI
    │
    └── fastapi      → waits for postgres + opensearch healthy
                     → docker build (150s first time, cached after)
                     → uvicorn starts → lifespan() runs
                     → create_tables() → papers table created
                     → yield → app ready

GET /api/v1/health → {"status": "ok", "checks": {"postgres": "healthy"}}
```

The final `GET /api/v1/health` response confirms that every layer of the stack is working — FastAPI is running, it has a live connection to PostgreSQL, and the entire boot sequence completed without errors. This single endpoint is the acceptance test for the entire Week 1 build.

---

## Key Engineering Decisions

| Decision | Alternative | Why This Choice |
|----------|-------------|-----------------|
| `python:3.13-slim` base image | Full `python:3.13` | 3× smaller image, fewer installed packages, smaller attack surface |
| Copy dependency files before source code | Copy everything at once | Docker layer caching prevents full reinstall on every code change |
| `depends_on: condition: service_healthy` | Basic `depends_on` | Container start does not equal service ready — prevents startup race conditions |
| arXiv ID as primary key | Auto-increment integer | Free deduplication; meaningful, human-readable identifiers in URLs |
| `yield` in `get_db()` | Manual `return` + close | Guarantees session close on exceptions — structurally eliminates connection leaks |
| Pydantic Settings over `os.getenv()` | Scattered `os.getenv()` calls | Type safety, fail-fast on missing config, single source of truth |
| Named Docker volumes | Bind mounts to local folders | Named volumes survive container deletion; bind mounts are OS-specific |

---

## What's Next (Week 2)

- Airflow DAG for daily arXiv ingestion across `cs.AI`, `cs.LG`, and `cs.CL` categories
- Docling PDF parsing pipeline for extracting structured content from research papers
- Jina AI embeddings for converting paper text into dense vectors for semantic search
- OpenSearch index configured with a dense vector field for similarity search
- End-to-end pipeline: paper fetched from arXiv → parsed → embedded → indexed → searchable via API
