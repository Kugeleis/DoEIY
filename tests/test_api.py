from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_read_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert b"DoEIY" in response.content


def test_api_version() -> None:
    response = client.get("/api/version")
    assert response.status_code == 200
    assert "version" in response.json()
    assert response.json()["version"] == "1.0.2"
