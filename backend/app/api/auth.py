from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.exc import IntegrityError

from app.api.schemas import LoginInput, RegistrationInput, UserView
from app.api.security import DB, CurrentUser, cookie_name, require_trusted_origin
from app.core.config import get_settings
from app.models import User
from app.services.auth import PASSWORDS, authenticate, create_session, revoke_session

router = APIRouter(prefix="/auth", tags=["authentication"])
trusted_origin = [Depends(require_trusted_origin)]


@router.post("/register", response_model=UserView, status_code=201, dependencies=trusted_origin)
def register(payload: RegistrationInput, db: DB) -> User:
    user = User(
        email=payload.email, password_hash=PASSWORDS.hash(payload.password.get_secret_value())
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        if getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "uq_users_email":
            raise HTTPException(
                status_code=409, detail="An account already uses this email."
            ) from None
        raise
    return user


@router.post("/login", response_model=UserView, dependencies=trusted_origin)
def login(payload: LoginInput, request: Request, response: Response, db: DB) -> User:
    user = authenticate(db, payload.email, payload.password.get_secret_value())
    if user is None:
        raise HTTPException(status_code=401, detail="Email or password is incorrect.")

    settings = get_settings()
    revoke_session(db, request.cookies.get(cookie_name()))
    token = create_session(db, user, settings.session_ttl_minutes)
    db.commit()
    response.set_cookie(
        cookie_name(),
        token,
        max_age=settings.session_ttl_minutes * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )
    return user


@router.post("/logout", status_code=204, dependencies=trusted_origin)
def logout(request: Request, response: Response, db: DB) -> None:
    revoke_session(db, request.cookies.get(cookie_name()))
    db.commit()
    response.delete_cookie(
        cookie_name(), httponly=True, secure=get_settings().session_cookie_secure, samesite="lax"
    )


@router.get("/me", response_model=UserView)
def me(user: CurrentUser) -> User:
    return user
