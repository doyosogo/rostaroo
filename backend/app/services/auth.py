from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import AuthSession, User

PASSWORDS = PasswordHasher()
# Equalise password verification work when a submitted email does not exist.
DUMMY_HASH = PASSWORDS.hash("Rostaroo dummy verification input")


def token_digest(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def find_session_user(db: Session, token: str | None) -> User | None:
    if not token or len(token) != 43:
        return None
    return db.scalar(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.token_hash == token_digest(token),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )


def revoke_session(db: Session, token: str | None) -> None:
    if token and len(token) == 43:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == token_digest(token)))


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    stored_hash = user.password_hash if user else DUMMY_HASH
    try:
        PASSWORDS.verify(stored_hash, password)
    except (InvalidHashError, VerificationError):
        return None
    if user and PASSWORDS.check_needs_rehash(stored_hash):
        user.password_hash = PASSWORDS.hash(password)
    return user


def create_session(db: Session, user: User, ttl_minutes: int) -> str:
    token = token_urlsafe(32)
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_digest(token),
            expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
        )
    )
    return token
