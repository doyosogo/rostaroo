# Rostaroo

Rostaroo is a workforce management application for Australian hospitality, starting with cafés, restaurants and small businesses in Adelaide, South Australia. Owners and managers will be able to organise their teams and publish weekly rosters. Employees will be able to see upcoming shifts and manage their availability and requests.

## Milestone 02 · Owner accounts and organisations

Owners can register, log in and create an organisation. Rostaroo restores valid sessions on refresh, sends accounts without an organisation to onboarding and shows members their organisation dashboard. Logout revokes the browser's session. The health endpoint still runs without a database connection.

Employee management, invitations, weekly rosters, upcoming shifts, availability, leave, shift swaps, staffing checks and payroll are outside this milestone.

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
│   └── src/                 # Owner workflows, API client, styles and tests
└── backend/
    ├── app/
    │   ├── api/             # HTTP routes
    │   ├── core/            # Environment settings
    │   ├── db/              # Database URL and SQLAlchemy base
    │   ├── models/          # User, organisation, membership and session models
    │   └── services/        # Authentication and token handling
    ├── migrations/          # Alembic environment and schema revisions
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

Open http://127.0.0.1:5173 to open the owner registration and login flows. The dev server uses a fixed port so it stays aligned with the API's default CORS origins.

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

Expected response is `{"status":"ok"}`. Interactive API docs are at http://127.0.0.1:8000/docs. The health route and its tests run without PostgreSQL or a local environment file. To use registration, login and organisations, start PostgreSQL and apply the migrations first.

### Configure and run PostgreSQL

From the repository root, create `.env` from the example if you have not already done so.

```sh
cp -n .env.example .env
docker compose config --quiet
docker compose up -d --wait db
docker compose ps db
(cd backend && .venv/bin/alembic upgrade head && .venv/bin/alembic current)
```

`.env` is ignored by Git. Use the example values only for local development. Compose and FastAPI both read the root file. Shell environment values take precedence in each process.

| Variable | Purpose |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Initialise a new PostgreSQL volume and configure the backend's connection |
| `POSTGRES_PORT` | Published localhost port, defaulting to `55432`. Change it if another project uses that port |
| `CORS_ORIGINS` | Exact frontend origins as a JSON array. Defaults to `["http://127.0.0.1:5173","http://localhost:5173"]` |
| `SESSION_COOKIE_SECURE` | Defaults to `false` for local HTTP. Use `true` with HTTPS and explicitly configured HTTPS origins |
| `SESSION_TTL_MINUTES` | Fixed session lifetime. Default `480`, allowed range `5` to `720` |
| `VITE_API_ORIGIN` | Optional public API origin in ignored `frontend/.env.local`. Localhost defaults to port `8000` on the same hostname as the frontend. Other hosts default to same-origin API paths |

The database is published on `127.0.0.1` and stores data in the `postgres_data` named volume. Compose reports health using `pg_isready`. Initialisation variables apply when the volume is first created. Editing them later requires coordinating changes with the database inside the existing volume.

Use `docker compose stop db` to stop PostgreSQL and keep the data. Revision `0001_accounts` creates the Milestone 02 schema. From `backend/`, run `.venv/bin/alembic check` to compare the live schema with the SQLAlchemy models. Downgrading this initial migration removes its tables and data.

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

`alembic current` checks the database's revision state without applying migrations. Expect revision `0001_accounts (head)` when you run `alembic current` without output redirection.

## Authentication and organisation access

| Endpoint | Behaviour |
| --- | --- |
| `POST /api/auth/register` | Normalises the email, validates a 15–128-character password and creates an account with an Argon2id hash |
| `POST /api/auth/login` | Verifies credentials and sets an opaque session cookie |
| `GET /api/auth/me` | Returns the signed-in user's ID and email |
| `POST /api/auth/logout` | Revokes the presented session in PostgreSQL and clears the cookie |
| `POST /api/organisations` | Creates a business with a name, suburb and Australian state or territory, and adds the creator as owner |
| `GET /api/organisations` | Lists organisations for the signed-in user's memberships |
| `GET /api/organisations/{id}` | Returns organisation details and the caller's role when the caller is a member |

The cookie is host-only, HttpOnly and SameSite=Lax. HTTPS mode adds Secure and uses the `__Host-` prefix. The browser holds the random token and PostgreSQL holds its SHA-256 digest and expiry. The server checks expiry on each authenticated request. A fresh login replaces the presented session, and logout revokes that session immediately for subsequent requests. The frontend uses credentialed fetch and keeps no authentication tokens in local storage. For local testing, use the same host spelling across frontend and backend.

All POST routes require both a browser `Origin` exactly matching the configured allowlist and the `X-Rostaroo-CSRF: 1` header. This header causes a browser to preflight cross-origin calls. CORS only grants credentialed calls from allowed origins. The API checks both headers before mutation, including at login and registration. The header is a marker and contains no credential. TLS and a same-site frontend and API are expected for an HTTPS deployment.

### Database schema

- `users` stores UUIDs, unique normalised emails and Argon2id password hashes.
- `organisations` stores UUIDs, names, suburbs and Australian state or territory codes.
- `organisation_memberships` links users to organisations with a composite primary key and a constrained `owner`, `manager` or `employee` role.
- `auth_sessions` links users to unique token digests and uses indexes for user and expiry lookups. PostgreSQL stores timestamps as timezone-aware instants.

Onboarding locks the user row before checking whether the user already belongs to an organisation. It writes the organisation and owner membership in one transaction. Organisation lookups always filter by caller membership. A missing or inaccessible organisation returns 404. The schema supports future invitations and multiple members.

### Local owner walkthrough

1. Apply the migration and start the frontend and backend using the commands above.
2. Open the frontend, create a synthetic owner account using an `example.com` address and a local test passphrase.
3. Create a synthetic organisation with a suburb and state or territory, then confirm the dashboard shows its name.
4. Refresh to check session restoration. Log out, then log in again and confirm the organisation is retained.

Email verification, password recovery, employee invitations, rate limiting and automatic expiry-row cleanup are future work. Duplicate registration reports a conflict, which reveals that an address is registered. Keep this milestone in trusted local development. Treat the CORS origins as trusted code and keep HTTPS enabled for any non-local use.

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

### PostgreSQL integration tests

With the development Compose service running, provision a separate empty PostgreSQL database once from the repository root. Use a dedicated name matching `rostaroo_*_test`.

```sh
docker compose exec -T db sh -c 'createdb --username "$POSTGRES_USER" --maintenance-db "$POSTGRES_DB" rostaroo_m02_test'
(cd backend && ROSTAROO_TEST_DATABASE=rostaroo_m02_test .venv/bin/python -m pytest)
```

The tests reuse the configured local PostgreSQL host, port and role but explicitly select the test database. They reject the development database name and databases with unexpected tables. The suite applies Alembic, checks schema consistency and rolls back each test's data changes with an outer transaction. When the test database name is unset, only the tests that require PostgreSQL are skipped.

## Development dependency security note

As of 18 November 2026, the full frontend npm audit reports 11 high-severity entries from one advisory affecting `picomatch@4.0.7`. Vite and Vitest pull it in directly and through `tinyglobby`. The TypeScript ESLint parser also reaches it through `typescript-estree` and `tinyglobby`. The package is development-only in this repository, and `npm audit --omit=dev` reported zero findings. The latest published version is affected and the advisory lists no patch. [GitHub advisory](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)

The vulnerability can hang a Node.js tooling process that processes a malicious glob pattern. The residual risk is acceptable for trusted local development because Vite binds to loopback and the current project gives users no way to supply glob patterns to its tooling. Keep this finding open, continue running the full `npm audit` from `frontend/`, and update the lockfile and rerun the frontend checks when a compatible patch is available. Reassess before exposing the development tooling or processing untrusted glob patterns.
