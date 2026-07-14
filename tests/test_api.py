"""Tests for the FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient

from nexus_verify.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_providers(client: TestClient) -> None:
    response = client.get("/providers")
    assert response.status_code == 200
    names = {p["name"] for p in response.json()}
    assert "ddddocr" in names


def test_list_tasks(client: TestClient) -> None:
    response = client.get("/tasks")
    assert response.status_code == 200
    task_types = {t["task_type"] for t in response.json()}
    assert "captcha" in task_types


def test_verify_missing_provider(client: TestClient, sample_image_b64: str) -> None:
    payload = {
        "task_type": "captcha",
        "image_b64": sample_image_b64,
        "provider": "nonexistent",
    }
    response = client.post("/verify", json=payload)
    assert response.status_code == 200
    assert response.json()["code"] == 404
