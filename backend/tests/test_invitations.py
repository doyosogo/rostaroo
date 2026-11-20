from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.api.security import cookie_name
from app.db.session import get_db
from app.main import app
from app.models import Membership, Organisation, OrganisationInvitation, User
from app.services.auth import token_digest

HEADERS = {"Origin": "http://127.0.0.1:5173", "X-Rostaroo-CSRF": "1"}
BUSINESS = {"name": "Invitation Test Cafe", "suburb": "Adelaide", "state": "SA"}


def sign_up(client, label):
    account = {
        "email": f"{label}-{uuid4().hex}@example.com",
        "password": "synthetic invitation passphrase",
    }
    response = client.post("/api/auth/register", json=account, headers=HEADERS)
    assert response.status_code == 201
    login = client.post("/api/auth/login", json=account, headers=HEADERS)
    assert login.status_code == 200
    return response.json()


def create_org(client):
    response = client.post("/api/organisations", json=BUSINESS, headers=HEADERS)
    assert response.status_code == 201
    return response.json()["id"]


def org_path(org_id):
    return f"/api/organisations/{org_id}"


def invite(client, org_id, email, role="employee"):
    return client.post(
        f"{org_path(org_id)}/invitations", json={"email": email, "role": role}, headers=HEADERS
    )


def accept(client, code):
    return client.post("/api/invitations/accept", json={"code": code}, headers=HEADERS)


def revoke(client, org_id, invitation_id):
    return client.post(f"{org_path(org_id)}/invitations/{invitation_id}/revoke", headers=HEADERS)


def add_member(connection, org_id, member, role):
    connection.execute(
        Membership.__table__.insert().values(
            organisation_id=UUID(org_id), user_id=UUID(member["id"]), role=role
        )
    )


@pytest.mark.parametrize("role", ["employee", "manager"])
def test_owner_creates_invitation_and_only_creation_exposes_code(client, test_connection, role):
    owner = sign_up(client, "owner")
    org_id = create_org(client)
    response = invite(client, org_id, "  Invited@Example.COM  ", role)
    assert response.status_code == 201
    assert response.headers["cache-control"] == "no-store"
    created = response.json()
    assert len(created["code"]) == 43
    assert created["invited_email"] == "invited@example.com"
    assert created["invited_role"] == role

    stored = test_connection.execute(
        select(OrganisationInvitation.__table__).where(
            OrganisationInvitation.id == UUID(created["id"])
        )
    ).one()
    assert stored.token_digest == token_digest(created["code"])
    assert stored.token_digest != created["code"]
    assert str(stored.created_by_user_id) == owner["id"]
    assert stored.expires_at - stored.created_at == timedelta(days=7)

    public = {key: value for key, value in created.items() if key != "code"}
    assert client.get(f"{org_path(org_id)}/invitations").json() == [public]
    assert invite(client, org_id, "invited@example.com", "manager").status_code == 409
    assert invite(client, org_id, owner["email"]).status_code == 409
    assert revoke(client, org_id, created["id"]).status_code == 204
    assert client.get(f"{org_path(org_id)}/invitations").json() == []
    assert invite(client, org_id, "invited@example.com").status_code == 201


def test_manager_can_manage_employee_invitations_only(client, test_connection):
    sign_up(client, "owner")
    org_id = create_org(client)
    manager_invite = invite(client, org_id, "manager-invite@example.com", "manager").json()
    manager = sign_up(client, "manager")
    add_member(test_connection, org_id, manager, "manager")

    assert client.get(f"{org_path(org_id)}/members").status_code == 200
    assert invite(client, org_id, "other@example.com", "manager").status_code == 403
    assert invite(client, org_id, "other@example.com", "owner").status_code == 422
    response = invite(client, org_id, "other@example.com")
    assert response.status_code == 201
    assert [row["id"] for row in client.get(f"{org_path(org_id)}/invitations").json()] == [
        response.json()["id"]
    ]
    assert revoke(client, org_id, manager_invite["id"]).status_code == 404
    assert revoke(client, org_id, response.json()["id"]).status_code == 204


def test_membership_permissions_and_cross_organisation_isolation(client, test_connection):
    sign_up(client, "owner")
    org_a = create_org(client)
    invitation = invite(client, org_a, "invited@example.com").json()
    client.cookies.clear()
    assert client.get(f"{org_path(org_a)}/members").status_code == 401
    assert client.get(f"{org_path(org_a)}/invitations").status_code == 401
    assert invite(client, org_a, "another@example.com").status_code == 401
    assert revoke(client, org_a, invitation["id"]).status_code == 401
    assert accept(client, invitation["code"]).status_code == 401

    employee = sign_up(client, "employee")
    add_member(test_connection, org_a, employee, "employee")
    assert client.get(org_path(org_a)).json()["role"] == "employee"
    assert client.get(f"{org_path(org_a)}/members").status_code == 403
    assert client.get(f"{org_path(org_a)}/invitations").status_code == 403
    assert invite(client, org_a, "another@example.com").status_code == 403
    assert revoke(client, org_a, invitation["id"]).status_code == 403

    sign_up(client, "other-owner")
    org_b = create_org(client)
    assert client.get(f"{org_path(org_a)}/members").status_code == 404
    assert client.get(f"{org_path(org_a)}/invitations").status_code == 404
    assert invite(client, org_a, "another@example.com").status_code == 404
    assert revoke(client, org_a, invitation["id"]).status_code == 404
    assert revoke(client, org_b, invitation["id"]).status_code == 404


@pytest.mark.parametrize("state", ["expired", "revoked", "pending"])
def test_acceptance_lifecycle_and_recipient_binding(client, test_connection, state):
    recipient = sign_up(client, "recipient")
    recipient_session = client.cookies.get(cookie_name())
    client.cookies.clear()
    sign_up(client, "owner")
    org_id = create_org(client)
    invitation = invite(client, org_id, recipient["email"], "manager").json()
    code = invitation["code"]
    assert accept(client, code).status_code == 400

    if state == "expired":
        now = datetime.now(UTC)
        test_connection.execute(
            update(OrganisationInvitation)
            .where(OrganisationInvitation.id == UUID(invitation["id"]))
            .values(created_at=now - timedelta(days=8), expires_at=now - timedelta(days=1))
        )
        assert client.get(f"{org_path(org_id)}/invitations").json() == []
        assert revoke(client, org_id, invitation["id"]).status_code == 404
    if state == "revoked":
        assert revoke(client, org_id, invitation["id"]).status_code == 204

    client.cookies.clear()
    client.cookies.set(cookie_name(), recipient_session)
    assert accept(client, ("Z" if code[0] != "Z" else "Y") + code[1:]).status_code == 400
    if state in {"expired", "revoked"}:
        assert accept(client, code).status_code == 400
        assert client.get("/api/organisations").json() == []
    else:
        joined = accept(client, code)
        assert joined.status_code == 200
        assert joined.json()["id"] == org_id
        assert joined.json()["role"] == "manager"
        assert client.get("/api/organisations").json() == [joined.json()]
        assert client.get(f"{org_path(org_id)}/invitations").json() == []
        assert accept(client, code).status_code == 400


def test_invitation_cannot_add_second_membership(client, test_connection):
    recipient = sign_up(client, "existing")
    recipient_session = client.cookies.get(cookie_name())
    first_org = create_org(client)
    client.cookies.clear()
    sign_up(client, "other-owner")
    second_org = create_org(client)
    invitation = invite(client, second_org, recipient["email"]).json()
    client.cookies.clear()
    client.cookies.set(cookie_name(), recipient_session)
    assert accept(client, invitation["code"]).status_code == 409
    assert [row["id"] for row in client.get("/api/organisations").json()] == [first_org]
    assert (
        test_connection.scalar(
            select(OrganisationInvitation.accepted_at).where(
                OrganisationInvitation.id == UUID(invitation["id"])
            )
        )
        is None
    )


def test_invalid_input_and_csrf(client):
    sign_up(client, "owner")
    org_id = create_org(client)
    assert invite(client, org_id, "invalid").status_code == 422
    assert invite(client, org_id, "invited@example.com", "owner").status_code == 422
    assert accept(client, "short").status_code == 400
    invited = invite(client, org_id, "invited@example.com").json()
    paths = [
        f"{org_path(org_id)}/invitations",
        f"{org_path(org_id)}/invitations/{invited['id']}/revoke",
        "/api/invitations/accept",
    ]
    for path in paths:
        assert client.post(path, headers={"Origin": HEADERS["Origin"]}).status_code == 403


def test_concurrent_redemption_uses_independent_transactions(test_engine):
    def isolated_db():
        with Session(test_engine, expire_on_commit=False) as session:
            yield session

    app.dependency_overrides[get_db] = isolated_db
    fixture_users = []
    org_id = None
    try:
        with TestClient(app, base_url="https://testserver") as client:
            recipient = sign_up(client, "parallel-recipient")
            fixture_users.append(UUID(recipient["id"]))
            recipient_session = client.cookies.get(cookie_name())
            client.cookies.clear()
            owner = sign_up(client, "parallel-owner")
            fixture_users.append(UUID(owner["id"]))
            org_id = create_org(client)
            code = invite(client, org_id, recipient["email"]).json()["code"]

            start = Barrier(2)

            def redeem():
                with TestClient(app, base_url="https://testserver") as other:
                    other.cookies.set(cookie_name(), recipient_session)
                    start.wait(timeout=5)
                    return accept(other, code).status_code

            with ThreadPoolExecutor(max_workers=2) as workers:
                attempts = [workers.submit(redeem) for _ in range(2)]
                assert sorted(attempt.result(timeout=10) for attempt in attempts) == [200, 400]

            with test_engine.connect() as connection:
                assert (
                    connection.scalar(
                        select(func.count())
                        .select_from(Membership)
                        .where(Membership.user_id == fixture_users[0])
                    )
                    == 1
                )
    finally:
        app.dependency_overrides.pop(get_db)
        with test_engine.begin() as connection:
            if org_id is not None:
                connection.execute(delete(Organisation).where(Organisation.id == UUID(org_id)))
            if fixture_users:
                connection.execute(delete(User).where(User.id.in_(fixture_users)))
