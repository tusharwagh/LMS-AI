import pytest
from fastapi.testclient import TestClient

from lms.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app())


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_correlation_id_echoed(client: TestClient) -> None:
    response = client.get("/health", headers={"X-Correlation-Id": "test-corr-123"})
    assert response.status_code == 200
    assert response.headers.get("X-Correlation-Id") == "test-corr-123"
