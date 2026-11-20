from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models import AuthSession, Membership, User
from app.services.auth import PASSWORDS, token_digest

ORIGIN = "http://127.0.0.1:5173"
HEADERS = {"Origin": ORIGIN, "X-Rostaroo-CSRF": "1"}
ACCOUNT = {"email": "owner@example.com", "password": "synthetic portfolio passphrase"}
BUSINESS = {"name": "Example Cafe", "suburb": "Adelaide", "state": "SA"}


def register(client, account=ACCOUNT):
    return client.post("/api/auth/register", json=account, headers=HEADERS)


def login(client, account=ACCOUNT):
    return client.post("/api/auth/login", json=account, headers=HEADERS)


def test_registration_normalises_email_and_hashes_password(client, test_connection):
    response = register(client, {**ACCOUNT, "email": " OWNER@Example.COM "})
    assert response.status_code == 201
    assert set(response.json()) == {"id", "email"}
    assert response.json()["email"] == ACCOUNT["email"]
    row = test_connection.execute(
        select(User.__table__).where(User.email == ACCOUNT["email"])
    ).one()
    assert row.password_hash.startswith("$argon2id$")
    assert PASSWORDS.verify(row.password_hash, ACCOUNT["password"])
    assert row.created_at.utcoffset() == timedelta(0)
    assert register(client).status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {**ACCOUNT, "email": "invalid"},
        {**ACCOUNT, "password": "too short"},
        {**ACCOUNT, "password": "x" * 129},
    ],
)
def test_registration_rejects_invalid_input_without_echoing_it(payload):
    def no_db():
        yield None

    app.dependency_overrides[get_db] = no_db
    try:
        with TestClient(app) as client:
            response = register(client, payload)
        assert response.status_code == 422
        assert response.json() == {"detail": "Check the information you entered."}
    finally:
        app.dependency_overrides.pop(get_db)


def test_login_current_user_and_logout_revoke_cookie(client, test_connection):
    assert register(client).status_code == 201
    assert login(client, {**ACCOUNT, "password": "wrong synthetic passphrase"}).status_code == 401
    response = login(client)
    assert response.status_code == 200
    assert set(response.json()) == {"id", "email"}
    assert response.headers["cache-control"] == "no-store"
    cookie = next(iter(client.cookies.jar))
    assert len(cookie.value) == 43
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    own_session = select(AuthSession.token_hash).where(
        AuthSession.user_id == UUID(response.json()["id"])
    )
    assert test_connection.scalar(own_session) == token_digest(cookie.value)

    assert client.get("/api/auth/me").json() == response.json()
    assert client.post("/api/auth/logout", headers=HEADERS).status_code == 204
    assert test_connection.scalar(own_session) is None
    replay = client.get("/api/auth/me", headers={"Cookie": f"{cookie.name}={cookie.value}"})
    assert replay.status_code == 401


def test_expired_session_and_login_rotation(client, test_connection):
    assert register(client).status_code == 201
    assert login(client).status_code == 200
    old_cookie = next(iter(client.cookies.jar))
    assert login(client).status_code == 200
    new_cookie = next(iter(client.cookies.jar))
    assert token_digest(new_cookie.value) != token_digest(old_cookie.value)
    assert (
        client.get(
            "/api/auth/me", headers={"Cookie": f"{old_cookie.name}={old_cookie.value}"}
        ).status_code
        == 401
    )
    now = datetime.now(UTC)
    test_connection.execute(
        AuthSession.__table__.update()
        .where(AuthSession.token_hash == token_digest(new_cookie.value))
        .values(created_at=now - timedelta(hours=2), expires_at=now - timedelta(hours=1))
    )
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/organisations").status_code == 401


def test_organisation_onboarding_and_isolation(client, test_connection):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/organisations").status_code == 401
    assert client.post("/api/organisations", json=BUSINESS, headers=HEADERS).status_code == 401

    assert register(client).status_code == 201
    owner = login(client).json()
    assert client.get("/api/organisations").json() == []
    assert (
        client.post(
            "/api/organisations", json={**BUSINESS, "state": "XX"}, headers=HEADERS
        ).status_code
        == 422
    )
    created = client.post("/api/organisations", json=BUSINESS, headers=HEADERS)
    assert created.status_code == 201
    organisation = created.json()
    assert organisation == {**BUSINESS, "id": organisation["id"], "role": "owner"}
    membership = test_connection.execute(
        select(Membership.__table__).where(Membership.user_id == UUID(owner["id"]))
    ).one()
    assert str(membership.user_id) == owner["id"]
    assert str(membership.organisation_id) == organisation["id"]
    assert membership.role == "owner"
    assert client.post("/api/organisations", json=BUSINESS, headers=HEADERS).status_code == 409

    path = f"/api/organisations/{organisation['id']}"
    assert client.get(path).json() == organisation
    assert client.get("/api/organisations").json() == [organisation]
    second_account = {**ACCOUNT, "email": "second-owner@example.com"}
    assert register(client, second_account).status_code == 201
    assert login(client, second_account).status_code == 200
    assert client.get(path).status_code == 404
    assert client.get("/api/organisations").json() == []
    second_org = client.post(
        "/api/organisations", json={**BUSINESS, "name": "Another Cafe"}, headers=HEADERS
    )
    assert second_org.status_code == 201
    assert client.get("/api/organisations").json() == [second_org.json()]
    assert client.get(path).status_code == 404


@pytest.mark.parametrize("path", ["auth/register", "auth/login", "auth/logout", "organisations"])
@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": ORIGIN},
        {"X-Rostaroo-CSRF": "1"},
        {"Origin": "https://example.invalid", "X-Rostaroo-CSRF": "1"},
    ],
)
def test_csrf_rejected_before_database_access(path, headers):
    def no_db():
        pytest.fail("CSRF request reached the database dependency")

    app.dependency_overrides[get_db] = no_db
    try:
        with TestClient(app) as client:
            assert client.post(f"/api/{path}", json=ACCOUNT, headers=headers).status_code == 403
    finally:
        app.dependency_overrides.pop(get_db)


def test_credentialed_cors_preflight():
    headers = {
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type,x-rostaroo-csrf",
    }
    with TestClient(app) as client:
        allowed = client.options("/api/auth/login", headers={**headers, "Origin": ORIGIN})
        blocked = client.options(
            "/api/auth/login", headers={**headers, "Origin": "https://example.invalid"}
        )
    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == ORIGIN
    assert allowed.headers["access-control-allow-credentials"] == "true"
    assert blocked.status_code == 400
    assert "access-control-allow-origin" not in blocked.headers


@pytest.mark.parametrize(
    ("origin", "secure"),
    [("*", True), ("https://app.example.com", False), ("http://app.example.com", True)],
)
def test_settings_reject_unsafe_frontend_origins(origin, secure):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cors_origins=[origin], session_cookie_secure=secure)


def test_https_cookie_uses_host_prefix_and_secure_flag(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "session_cookie_secure", True)
    assert register(client).status_code == 201
    response = login(client)
    assert response.status_code == 200
    header = response.headers["set-cookie"].lower()
    assert header.startswith("__host-rostaroo_session=")
    assert "; secure" in header
    assert "; httponly" in header
    assert "; path=/" in header
    assert "; domain=" not in header
    assert client.get("/api/auth/me").status_code == 200


def test_existing_members_can_read_only_their_organisation(client, test_connection):
    assert register(client).status_code == 201
    assert login(client).status_code == 200
    organisation = client.post("/api/organisations", json=BUSINESS, headers=HEADERS).json()

    account = {**ACCOUNT, "email": "member@example.com"}
    assert register(client, account).status_code == 201
    member = login(client, account).json()
    test_connection.execute(
        Membership.__table__.insert().values(
            user_id=UUID(member["id"]), organisation_id=UUID(organisation["id"]), role="employee"
        )
    )
    assert client.get(f"/api/organisations/{organisation['id']}").json() == {
        **organisation,
        "role": "employee",
    }
    assert client.post("/api/organisations", json=BUSINESS, headers=HEADERS).status_code == 409
