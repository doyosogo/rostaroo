# Rostaroo

Rostaroo is a workforce management application for Australian hospitality, starting with cafés, restaurants and small businesses in Adelaide, South Australia. Owners and managers will be able to organise their teams and publish weekly rosters. Employees will be able to see upcoming shifts and manage their availability and requests.

## Milestone 01 · Project foundation

The frontend presents a welcome screen and development status. The FastAPI backend provides a database-independent health endpoint. SQLAlchemy and Alembic are configured for future schema changes, and Docker Compose defines a local PostgreSQL service.

The planned MVP includes organisation and employee management, weekly roster creation and publication, upcoming shifts, weekly availability, leave and shift swap requests, manager approvals and declines, and checks for overlapping shifts and staffing conflicts. Sign-in and all workforce features are future work.

## Stack and layout

| Area | Tools |
| --- | --- |
| Frontend | React, TypeScript, Vite, Tailwind CSS, Vitest, ESLint and Prettier |
| Backend | Python, FastAPI, Uvicorn, SQLAlchemy, Alembic, Psycopg, Pytest and Ruff |
| Local database | PostgreSQL and Docker Compose |

```text
rostaroo/
├── AGENTS.md
├── README.md
├── .gitignore
├── .env.example
├── compose.yaml
├── frontend/
│   └── src/                 # Welcome screen, styles and component test
└── backend/
    ├── app/
    │   ├── api/             # HTTP routes
    │   ├── core/            # Environment settings
    │   ├── db/              # Database URL and SQLAlchemy base
    │   ├── models/          # Reserved for future database models
    │   └── services/        # Reserved for future business logic
    ├── migrations/          # Alembic environment and future revisions
    └── tests/               # API tests
```

## Local setup

You need Git, Node.js 22.13+ in the 22.x line or Node.js 24.x with npm, and Python 3.12. To run PostgreSQL, also have Docker Engine running in an Apple Silicon-compatible Linux VM and the Docker Compose v2 CLI available. The Docker Official PostgreSQL image supports ARM64.

From the repository root, install the frontend and backend dependencies.

```sh
(cd frontend && npm ci)
python3.12 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements-dev.txt
```

### Run the frontend

```sh
cd frontend
npm run dev
```

Open http://127.0.0.1:5173 to see the welcome screen. The dev server uses a fixed port so it stays aligned with the API's default CORS origins.

### Run the API

In a separate terminal, from the repository root:

```sh
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

From another terminal:

```sh
curl --fail --silent --show-error http://127.0.0.1:8000/api/health
```

Expected response is `{"status":"ok"}`. Interactive API docs are at http://127.0.0.1:8000/docs. The health route and its tests run without PostgreSQL or a local environment file.

### Configure and run PostgreSQL

From the repository root, create `.env` from the example if you have not already done so.

```sh
cp -n .env.example .env
docker compose config --quiet
docker compose up -d --wait db
docker compose ps db
```

`.env` is ignored by Git. Use the example values only for local development. Compose and FastAPI both read the root file. Shell environment values take precedence in each process.

| Variable | Purpose |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Initialise a new PostgreSQL volume and configure the backend's connection |
| `POSTGRES_PORT` | Published localhost port, defaulting to `55432`. Change it if another project uses that port |
| `CORS_ORIGINS` | JSON array of allowed frontend origins. Defaults to `http://127.0.0.1:5173` and `http://localhost:5173` |

The database is published on `127.0.0.1` and stores data in the `postgres_data` named volume. Compose reports health using `pg_isready`. Initialisation variables apply when the volume is first created. Editing them later requires coordinating changes with the database inside the existing volume.

Use `docker compose stop db` to stop PostgreSQL and keep the data. Alembic is ready for future migrations. From `backend/`, run `.venv/bin/alembic heads` to inspect the revision history, which is empty in this milestone.

### Verify the live database from Terminal 2

After starting the local Docker engine, run the PostgreSQL setup commands above from the repository root. The `ps` output should show `db` as healthy. Then run the following from the same root to verify the application's SQLAlchemy connection and Alembic's live database access:

```sh
(
  cd backend &&
  .venv/bin/python - <<'PY'
from sqlalchemy import create_engine, text
from app.db.config import get_database_url

try:
    engine = create_engine(get_database_url())
    try:
        with engine.connect() as connection:
            if connection.execute(text("SELECT 1")).scalar_one() != 1:
                raise RuntimeError("Unexpected query result")
    finally:
        engine.dispose()
except Exception:
    raise SystemExit("Database connectivity check failed. Check the service and local configuration.")

print("PostgreSQL SELECT 1 passed")
PY
) &&
(
  cd backend &&
  if .venv/bin/alembic current >/dev/null 2>&1; then
    printf '%s\n' 'Alembic live database check passed'
  else
    printf '%s\n' 'Alembic live database check failed' >&2
    exit 1
  fi
)
```

`alembic current` checks the database's revision state without applying migrations. There is no current revision in Milestone 01.

## Tests and checks

From the repository root:

```sh
cd frontend
npm run typecheck
npm run lint
npm run format:check
npm run test
npm run build
```

From the repository root in a separate shell:

```sh
cd backend
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

## Development dependency security note

As of 18 November 2026, the full frontend npm audit reports 11 high-severity entries from one advisory affecting `picomatch@4.0.7`. Vite and Vitest pull it in directly and through `tinyglobby`. The TypeScript ESLint parser also reaches it through `typescript-estree` and `tinyglobby`. The package is development-only in this repository, and `npm audit --omit=dev` reported zero findings. The latest published version is affected and the advisory lists no patch. [GitHub advisory](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)

The vulnerability can hang a Node.js tooling process that processes a malicious glob pattern. The residual risk is acceptable for trusted local development because Vite binds to loopback and the current project gives users no way to supply glob patterns to its tooling. Keep this finding open, continue running the full `npm audit` from `frontend/`, and update the lockfile and rerun the frontend checks when a compatible patch is available. Reassess before exposing the development tooling or processing untrusted glob patterns.
