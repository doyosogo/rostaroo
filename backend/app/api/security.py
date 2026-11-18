from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import User
from app.services.auth import find_session_user

DB = Annotated[Session, Depends(get_db)]
CSRF_HEADER = "X-Rostaroo-CSRF"


def cookie_name() -> str:
    return "__Host-rostaroo_session" if get_settings().session_cookie_secure else "rostaroo_session"


def require_trusted_origin(request: Request) -> None:
    if (
        request.headers.get("origin") not in get_settings().cors_origins
        or request.headers.get(CSRF_HEADER) != "1"
    ):
        raise HTTPException(status_code=403, detail="Request origin could not be verified.")


def current_user(request: Request, db: DB) -> User:
    user = find_session_user(db, request.cookies.get(cookie_name()))
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in.")
    return user


CurrentUser = Annotated[User, Depends(current_user)]
