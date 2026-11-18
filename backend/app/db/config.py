from sqlalchemy import URL

from app.core.config import get_settings


def get_database_url() -> URL:
    settings = get_settings()
    if not (settings.postgres_db and settings.postgres_user and settings.postgres_password):
        raise RuntimeError(
            "Set POSTGRES_DB, POSTGRES_USER and POSTGRES_PASSWORD before database use."
        )

    return URL.create(
        drivername="postgresql+psycopg",
        username=settings.postgres_user,
        password=settings.postgres_password.get_secret_value(),
        host="127.0.0.1",
        port=settings.postgres_port,
        database=settings.postgres_db,
    )
