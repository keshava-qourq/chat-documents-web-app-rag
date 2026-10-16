"""The document endpoints are stubs until the development sprint implements
them; these tests only prove the routes exist, are wired into the app and
return the typed placeholder every generated route returns. No Gemini,
storage or database behaviour is exercised here.
"""

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_documents_is_registered() -> None:
    response = client.get("/documents")

    assert response.status_code == 200
    assert response.json()["endpoint"] == "GET /documents"


def test_upload_documents_is_registered() -> None:
    response = client.post("/documents")

    assert response.status_code == 200
    assert response.json()["endpoint"] == "POST /documents"


def test_document_status_is_registered() -> None:
    response = client.get(f"/documents/{uuid.uuid4()}/status")

    assert response.status_code == 200
    assert response.json()["endpoint"] == "GET /documents/{id}/status"


def test_delete_document_is_registered() -> None:
    response = client.delete(f"/documents/{uuid.uuid4()}")

    assert response.status_code == 200
    assert response.json()["endpoint"] == "DELETE /documents/{id}"
