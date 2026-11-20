import os
import re
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.config import get_settings
from app.db.config import get_database_url
from app.db.session import get_db
from app.main import app


@pytest.fixture(scope="session")
def test_engine():
    name = os.getenv("ROSTAROO_TEST_DATABASE")
    if not name:
        pytest.skip("Set ROSTAROO_TEST_DATABASE to a dedicated PostgreSQL test database.")
    if not re.fullmatch(r"rostaroo_[a-z0-9_]+_test", name) or name == get_settings().postgres_db:
        pytest.fail("Use a dedicated rostaroo_*_test database distinct from development.")

    engine = create_engine(
        get_database_url().set(database=name), hide_parameters=True, poolclass=NullPool
    )
    try:
        with engine.begin() as connection:
            assert connection.scalar(text("SELECT current_database()")) == name
            tables = set(inspect(connection).get_table_names())
            expected = {
                "alembic_version",
                "users",
                "organisations",
                "organisation_memberships",
                "auth_sessions",
                "organisation_invitations",
            }
            previous = expected - {"organisation_invitations"}
            if tables not in (set(), previous, expected):
                pytest.fail("The configured test database contains unexpected tables.")
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            assert set(inspect(connection).get_table_names()) == expected
            command.check(config)
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def test_connection(test_engine):
    with test_engine.connect() as connection, connection.begin() as transaction:
        try:
            yield connection
        finally:
            transaction.rollback()


@pytest.fixture
def client(test_connection):
    def isolated_db():
        with Session(
            test_connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as session:
            yield session

    app.dependency_overrides[get_db] = isolated_db
    try:
        with TestClient(app, base_url="https://testserver") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db)
