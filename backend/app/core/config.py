from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, extra="ignore", hide_input_in_errors=True)

    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    postgres_db: str | None = None
    postgres_user: str | None = None
    postgres_password: SecretStr | None = None
    postgres_port: int = 55432
    session_cookie_secure: bool = False
    session_ttl_minutes: int = Field(default=480, ge=5, le=720)

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username is not None
                or origin != f"{parsed.scheme}://{parsed.netloc}"
                or "*" in origin
                or any(char.isspace() for char in origin)
            ):
                raise ValueError("Configure explicit HTTP or HTTPS origins without a path.")
        return origins

    @model_validator(mode="after")
    def validate_cookie_transport(self) -> "Settings":
        for origin in self.cors_origins:
            parsed = urlsplit(origin)
            if parsed.hostname not in {"localhost", "127.0.0.1", "::1"} and (
                parsed.scheme != "https" or not self.session_cookie_secure
            ):
                raise ValueError("Non-local frontend origins require HTTPS and secure cookies.")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
