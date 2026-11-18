from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.auth import router as auth_router
from app.api.health import router as health_router
from app.api.organisations import router as organisations_router
from app.api.security import CSRF_HEADER
from app.core.config import get_settings

app = FastAPI(title="Rostaroo API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=[CSRF_HEADER, "Content-Type"],
)
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(organisations_router, prefix="/api")


@app.exception_handler(RequestValidationError)
async def invalid_input(_request: Request, _error: RequestValidationError) -> JSONResponse:
    # Validation errors can contain submitted passwords and other private input.
    return JSONResponse(status_code=422, content={"detail": "Check the information you entered."})


@app.middleware("http")
async def prevent_private_response_caching(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith(("/api/auth/", "/api/organisations")):
        response.headers["Cache-Control"] = "no-store"
    return response
