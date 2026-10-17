"""The baseline test the scaffold ships with.

The platform installs this tree and runs `pytest` against it, so there has to
be something green to run before an agent has written anything -- otherwise the
first real ticket cannot tell a broken change from a repository that never
worked.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_ok(monkeypatch) -> None:
    """A failure here means the application does not import or does not start.

    `configured_services()` (app/services.py) reports whichever services'
    connection variables happen to be set in *whatever* environment pytest
    runs in -- it is not this suite's job to assume that environment is
    otherwise empty. `MINIO_ENDPOINT` and `GEMINI_API_KEY` are explicitly
    cleared here so this test's expectations of "unconfigured" hold
    regardless of what the ambient environment (CI, a developer's shell, an
    earlier test's leaked env var) happens to have set, rather than assuming
    a blank slate this test does not control.
    """
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert set(body["services"]) == {"minio", "gemini"}
    assert body["services"] == {"minio": False, "gemini": False}


def test_health_reports_each_service_as_configured_once_its_env_var_is_set(monkeypatch) -> None:
    """The complement of `test_health_reports_ok`: once a service's connection
    variable is set, `/health` reports it as configured -- proving the field
    tracks the environment rather than being hard-coded `False`."""
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["services"] == {"minio": True, "gemini": True}


def test_the_openapi_document_builds() -> None:
    """Every generated route contributes to the schema, so a route whose types
    FastAPI cannot resolve fails here rather than on a user's first request."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/documents" in paths
    assert "/documents/{document_id}/status" in paths
    assert "/threads" in paths
    assert "/threads/{thread_id}/messages" in paths
