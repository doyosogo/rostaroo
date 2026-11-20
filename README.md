# Rostaroo

Rostaroo is a workforce management application for Australian hospitality, starting with cafés, restaurants and small businesses in Adelaide, South Australia. Owners and managers will be able to organise their teams and publish weekly rosters. Employees will be able to see upcoming shifts and manage their availability and requests.

## Milestone 03 · Employee invitations and team management

Owners can register, create an organisation and manage their team. Owners and managers can see the team directory and issue or revoke invitations within their permissions. Invited employees and managers can sign in with the invited email, accept a one-time code and see their organisation membership. The health endpoint still runs without PostgreSQL.

Weekly rosters, upcoming shifts, availability, leave, shift swaps, staffing checks, payroll, time tracking and staff removal are future work.

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
│   └── src/                 # Account and team workflows, API client, styles and tests
└── backend/
    ├── app/
    │   ├── api/             # HTTP routes
    │   ├── core/            # Environment settings
    │   ├── db/              # Database URL and SQLAlchemy base
    │   ├── models/          # Account, membership and invitation models
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

Open http://127.0.0.1:5173 to register or log in. The dev server uses a fixed port so it stays aligned with the API's default CORS origins.

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

Use `docker compose stop db` to stop PostgreSQL and keep the data. Revision `0001_accounts` creates the account schema. Revision `0002_invitations` adds the invitations table and preserves existing accounts and memberships. Use `alembic upgrade head` to apply pending revisions. From `backend/`, run `.venv/bin/alembic check` to compare the live schema with the SQLAlchemy models. Downgrading either revision removes the tables and data that revision added.

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

`alembic current` checks the database's revision state without applying migrations. Expect revision `0002_invitations (head)` when you run `alembic current` without output redirection.

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
- `auth_sessions` links users to unique token digests and uses indexes for user and expiry lookups.
- `organisation_invitations` links an organisation and creator to an invited email and role. It stores a unique code digest, expiry and acceptance or revocation timestamp.

PostgreSQL stores timestamps as timezone-aware instants.

Onboarding locks the user row before checking whether the user already belongs to an organisation. It writes the organisation and owner membership in one transaction. Organisation lookups always filter by caller membership. A missing or inaccessible organisation returns 404. The schema supports multiple members per organisation. Self-service creation and invitation acceptance allow one organisation per user and use the same user-row lock.

## Team management and invitations

| Role | Permissions |
| --- | --- |
| Owner | See all team members. Create, list and revoke pending employee or manager invitations. |
| Manager | See all team members. Create, list and revoke pending employee invitations for the organisation. |
| Employee | See their own organisation membership. |

| Endpoint | Behaviour |
| --- | --- |
| `GET /api/organisations/{id}/members` | List member emails and roles for owners and managers |
| `POST /api/organisations/{id}/invitations` | Create an invitation from an email and role. The response contains its usable code once |
| `GET /api/organisations/{id}/invitations` | List pending invitations permitted for the caller's role, with expiry dates |
| `POST /api/organisations/{id}/invitations/{invitation_id}/revoke` | Revoke a permitted pending invitation |
| `POST /api/invitations/accept` | Consume a code supplied in the JSON body. The signed-in email must match the invitee |
| `GET /api/organisations` | Retrieve the caller's memberships and current roles |

The server checks membership and role for the requested organisation. An invitation is pending until it is accepted, revoked or reaches its seven-day expiry. An organisation can have one pending invitation per normalised email and cannot invite an existing member. Separate organisations can invite the same address, but the first accepted membership prevents a second join. Acceptance adds the membership and records the redemption in one transaction.

Rostaroo uses 256 random bits for each code and stores only its SHA-256 digest. Codes travel in JSON and the creation response is marked `Cache-Control: no-store`. Codes are shown in the creation view and stay in memory until that view closes or the code is replaced or revoked. Copying places the code on the device clipboard. If a code is lost before it is shared, revoke the pending invitation and issue a fresh one.

### Local invitation walkthrough

1. Apply the migration and start the frontend and API using the commands above.
2. Register with a synthetic `example.com` account and create an organisation.
3. Open **Manage team**, enter a second synthetic email, choose **Employee**, and select **Create invitation**. Copy the code.
4. Open the frontend in another browser profile or private window. Register or log in using the invited email and enter the code under **Join a team**.
5. Verify that the employee sees the organisation and their own role. In the owner window, reopen **Manage team** to refresh the directory and check that the employee appears and the invitation is gone.
6. To test revocation, issue an invitation to another synthetic email, revoke it and try to accept its code using that account.

There is no email delivery. Share codes privately with the intended recipient. Matching the registered address and requiring the code reduces unauthorised redemption, while the address itself remains unverified. Keep this milestone in trusted local development. Email verification, password recovery, rate limiting and automatic cleanup of expired invitation or session rows are future work. Duplicate registration reveals that an address is registered. Role changes, owner transfers and member removal are outside this milestone.

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

With the development Compose service running, provision a separate empty PostgreSQL database once from the repository root. If you already have the dedicated database from Milestone 02, reuse it and skip `createdb`. Use a dedicated name matching `rostaroo_*_test`.

```sh
docker compose exec -T db sh -c 'createdb --username "$POSTGRES_USER" --maintenance-db "$POSTGRES_DB" rostaroo_m02_test'
(cd backend && ROSTAROO_TEST_DATABASE=rostaroo_m02_test .venv/bin/python -m pytest)
```

The tests reuse the configured local PostgreSQL host, port and role but explicitly select the test database. They reject the development database name and databases with unexpected tables. The suite applies Alembic and checks schema consistency. Most tests roll back their writes with an outer transaction. The concurrency test uses independent transactions and removes only the synthetic rows it creates. When the test database name is unset, only the tests that require PostgreSQL are skipped.

## Development dependency security note

Earlier milestone audits reported 11 high-severity entries tracing to the development dependency `picomatch@4.0.7`, which Vite, Vitest and TypeScript ESLint use. GitHub withdrew that advisory on 18 November 2026. On 20 November, both the full `npm audit` and `npm audit --omit=dev` reported zero findings with the existing lockfile. The advisory link is kept for the milestone record. Continue running the full audit from `frontend/`. [Withdrawn GitHub advisory](https://github.com/advisories/GHSA-fc5q-39xc-vjpf)
