from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_read_root() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert b"DoEIY" in response.content


def test_api_version() -> None:
    import os

    response = client.get("/api/version")
    assert response.status_code == 200
    assert "version" in response.json()

    expected_version = "1.0.2"
    version_file_path = os.path.join(os.path.dirname(__file__), "..", "version.txt")
    if os.path.exists(version_file_path):
        with open(version_file_path) as f:
            expected_version = f.read().strip()

    assert response.json()["version"] == expected_version
