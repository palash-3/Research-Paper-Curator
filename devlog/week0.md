# Week 0 — Project Scaffold & Toolchain Setup

**Project:** arXiv Research Paper Curator
**Date:** June 12, 2026
**Goal:** Establish the complete project foundation before writing a single line of application code.

---

## What I Built

Week 0 is pure scaffolding — the skeleton every future phase builds on. No application logic yet. Just the right folder structure, the right tools, and the right configuration to build a production-grade Python project from day one.

---

## Architecture Decision: UV over pip

Most Python tutorials still use `pip` + `venv`. I chose **UV** — a next-generation package manager written in Rust.

| Tool | Speed | Lockfile | Auto-venv |
|------|-------|----------|-----------|
| pip + venv | Slow | No (requires pip-tools) | No |
| poetry | Medium | Yes | Yes |
| **UV** | **10–100× faster** | **Yes (uv.lock)** | **Yes** |

UV creates and manages the virtual environment automatically. The `uv.lock` file pins every transitive dependency to an exact version — no more "it works on my machine" breakage when a sub-dependency silently upgrades.

```bash
uv init --python 3.13          # initialize project + .python-version
uv add fastapi uvicorn         # production deps → [project] in pyproject.toml
uv add --dev pytest ruff mypy  # dev deps → [dependency-groups.dev]
```

**Key distinction:** `--dev` keeps linters and test runners out of the production Docker image. Smaller image, cleaner deployments, better security.

---

## Directory Structure

```
Research-Paper-Curator/
├── src/                        # All application code
│   ├── models/                 # SQLAlchemy ORM models (Paper, Chunk)
│   ├── routers/                # FastAPI route handlers (health, search, ask)
│   └── services/               # Business logic (OpenSearch, Ollama, Redis)
├── airflow/
│   └── dags/                   # Scheduled ingestion pipeline DAGs
├── tests/                      # Pytest test suite
├── notebooks/                  # Jupyter notebooks for experimentation
├── pyproject.toml              # Single source of truth for project config
├── uv.lock                     # Exact pinned versions of all dependencies
├── .pre-commit-config.yaml     # Automated code quality on every commit
├── .python-version             # Pins Python 3.13 for UV
└── .env                        # Secrets — never committed to Git
```

Git tracks files, not folders. Empty directories are invisible to `git status`. I created placeholder `__init__.py` files so the package structure is real from the start.

---

## Dependency Architecture

**16 production libraries** selected with a clear purpose for each:

| Category | Library | Rationale |
|----------|---------|-----------|
| API | `fastapi`, `uvicorn` | Async-first, auto-generates OpenAPI docs |
| Database | `sqlalchemy`, `alembic`, `psycopg2-binary` | ORM + migrations + PostgreSQL driver |
| Search | `opensearch-py` | Vector + keyword hybrid search |
| HTTP | `httpx` | Async HTTP — required for non-blocking arXiv calls |
| Config | `pydantic-settings` | Typed env vars, fail-fast on startup |
| Ingestion | `arxiv`, `docling` | arXiv API + scientific PDF parsing |
| AI/Agents | `langgraph`, `langchain-core` | Agent workflow orchestration |
| Observability | `langfuse` | RAG tracing and monitoring |
| Cache | `redis` | Response caching for LLM queries |
| Delivery | `python-telegram-bot`, `gradio` | Telegram notifications + web UI |

**5 dev-only libraries:** `pytest`, `ruff`, `mypy`, `jupyter`, `pre-commit`

---

## Code Quality: Pre-commit Hooks

Every commit is automatically checked by Ruff before it reaches the repository.

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks:
      - id: ruff          # linting — catches unused imports, bad patterns
      - id: ruff-format   # formatting — enforces consistent code style
```

If Ruff finds an unfixable issue, the commit is **blocked**. This is a standard practice in professional engineering teams — bad-style code never enters the codebase.

---

## Configuration: pyproject.toml

Modern Python (since PEP 517/518) uses a single `pyproject.toml` as the project's source of truth:

```toml
[project]
name = "research-paper-curator"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.136.3",
    "uvicorn>=0.49.0",
    "sqlalchemy>=2.0.50",
    # ... 13 more
]

[dependency-groups]
dev = ["pytest>=9.0.3", "ruff>=0.15.17", "mypy>=2.1.0"]

[tool.ruff]
line-length = 88

[tool.mypy]
strict = true
```

One file for dependencies, tool config, and metadata. No separate `setup.py`, `requirements.txt`, or `tox.ini`.

---

## Git Workflow Established

```bash
git init
git branch -m master main          # modern convention
git add .
git commit -m "Phase 0: project basic structure ready"
```

`.gitignore` configured to exclude:
- `.env` — secrets
- `.venv/` — auto-generated, hundreds of MB
- `__pycache__/` — auto-generated bytecode
- `.DS_Store` — macOS system files

---

## Key Engineering Decisions

1. **Python 3.13** — best performance on Apple Silicon M5, full library support
2. **UV over Conda** — Conda was auto-activating from a prior install; disabled it and standardized on UV for this project
3. **`uv.lock` committed to Git** — ensures every environment (local, CI, Docker) gets identical library versions
4. **`src/` layout** — avoids import confusion between installed package and local edits

---

## What's Next (Week 1)

- Write `Dockerfile` to containerize the FastAPI app
- Write `compose.yml` to orchestrate all 6 microservices
- Implement typed config with Pydantic Settings
- Build the SQLAlchemy `Paper` model and database layer
- Wire up FastAPI with lifespan hooks and health endpoint
- Verify: `make health` → `{"status": "ok", "checks": {"postgres": "healthy"}}`
