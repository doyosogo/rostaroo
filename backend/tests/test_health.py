import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok():
    with TestClient(app) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    ("origin", "allowed"),
    [("http://127.0.0.1:5173", True), ("https://example.invalid", False)],
)
def test_health_cors(origin: str, allowed: bool):
    with TestClient(app) as client:
        response = client.get("/api/health", headers={"Origin": origin})

    assert response.headers.get("access-control-allow-origin") == (origin if allowed else None)
