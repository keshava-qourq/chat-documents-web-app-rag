"""The baseline test the scaffold ships with.

The platform installs this tree and runs `pytest` against it, so there has to
be something green to run before an agent has written anything -- otherwise the
first real ticket cannot tell a broken change from a repository that never
worked.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_ok() -> None:
    """A failure here means the application does not import or does not start."""
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    # Neither service's key is set in the test environment, so both report
    # unconfigured rather than this test reaching out to either of them.
    assert set(body["services"]) == {"minio", "gemini"}
    assert body["services"] == {"minio": False, "gemini": False}


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
