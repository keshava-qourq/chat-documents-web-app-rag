"""The thread and message endpoints are stubs until the development sprint
implements them; these tests only prove the routes exist, are wired into the
app and return the typed placeholder every generated route returns. No
Gemini, storage or database behaviour is exercised here.
"""

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_list_threads_is_registered() -> None:
    response = client.get("/threads")

    assert response.status_code == 200
    assert response.json()["endpoint"] == "GET /threads"


def test_create_thread_is_registered() -> None:
    response = client.post("/threads")

    assert response.status_code == 200
    assert response.json()["endpoint"] == "POST /threads"


def test_get_thread_is_registered() -> None:
    response = client.get(f"/threads/{uuid.uuid4()}")

    assert response.status_code == 200
    assert response.json()["endpoint"] == "GET /threads/{id}"


def test_rename_thread_is_registered() -> None:
    response = client.patch(f"/threads/{uuid.uuid4()}")

    assert response.status_code == 200
    assert response.json()["endpoint"] == "PATCH /threads/{id}"


def test_delete_thread_is_registered() -> None:
    response = client.delete(f"/threads/{uuid.uuid4()}")

    assert response.status_code == 200
    assert response.json()["endpoint"] == "DELETE /threads/{id}"


def test_post_message_is_registered() -> None:
    response = client.post(f"/threads/{uuid.uuid4()}/messages")

    assert response.status_code == 200
    assert response.json()["endpoint"] == "POST /threads/{id}/messages"
