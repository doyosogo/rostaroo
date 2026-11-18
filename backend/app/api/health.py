from typing import Literal

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
def health() -> dict[str, Literal["ok"]]:
    return {"status": "ok"}
