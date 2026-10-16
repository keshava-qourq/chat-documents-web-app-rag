"""Behavioural tests for the shared threads API: list, create, read, rename,
delete, and posting a question turn with auto-titling.

Each test gets its own in-memory SQLite database via the `client` fixture so
no shared state leaks between tests and no live database or MinIO is needed.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.services import derive_title


@pytest.fixture(autouse=True)
def _generous_rate_limits(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_HOUR", "1000000")
    monkeypatch.setenv("RATE_LIMIT_CHAT_PER_MIN", "1000000")


@pytest.fixture()
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def client(db_engine):
    db_sessionmaker = sessionmaker(bind=db_engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        session = db_sessionmaker()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_list_threads_empty_is_200_with_empty_list(client: TestClient) -> None:
    response = client.get("/threads")

    assert response.status_code == 200
    assert response.json() == []


def test_create_thread_returns_id_title_created_at_and_is_listed(client: TestClient) -> None:
    create_response = client.post("/threads")

    assert create_response.status_code == 200
    body = create_response.json()
    assert "id" in body
    assert "title" in body
    assert "created_at" in body

    list_response = client.get("/threads")
    assert list_response.status_code == 200
    listed = list_response.json()
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]
    assert "last_active_at" in listed[0]


def test_list_threads_orders_by_last_active_at_descending(client: TestClient) -> None:
    first = client.post("/threads").json()
    second = client.post("/threads").json()

    # Bump the first thread's activity after the second thread was created.
    client.post(f"/threads/{first['id']}/messages", json={"question": "hello"})

    listed = client.get("/threads").json()
    assert [t["id"] for t in listed] == [first["id"], second["id"]]


def test_list_threads_has_no_caller_filtering(client: TestClient) -> None:
    client.post("/threads")

    response_a = client.get("/threads", headers={"X-Forwarded-For": "1.1.1.1"})
    response_b = client.get("/threads", headers={"X-Forwarded-For": "2.2.2.2"})

    assert response_a.content == response_b.content


def test_get_unknown_thread_is_404(client: TestClient) -> None:
    response = client.get(f"/threads/{uuid.uuid4()}")

    assert response.status_code == 404


def test_get_thread_returns_title_and_message_history_with_citations(client: TestClient) -> None:
    created = client.post("/threads").json()
    thread_id = created["id"]

    client.post(f"/threads/{thread_id}/messages", json={"question": "What is the refund policy?"})

    detail = client.get(f"/threads/{thread_id}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["id"] == thread_id
    assert len(body["messages"]) == 1
    message = body["messages"][0]
    assert message["role"] == "user"
    assert message["content"] == "What is the refund policy?"
    assert message["citations"] == []


def test_post_message_appends_to_existing_thread_and_bumps_last_active(client: TestClient) -> None:
    created = client.post("/threads").json()
    thread_id = created["id"]

    response = client.post(f"/threads/{thread_id}/messages", json={"question": "First question"})
    assert response.status_code == 200
    assert response.json()["content"] == "First question"

    response2 = client.post(f"/threads/{thread_id}/messages", json={"question": "Second question"})
    assert response2.status_code == 200

    detail = client.get(f"/threads/{thread_id}").json()
    assert [m["content"] for m in detail["messages"]] == ["First question", "Second question"]


def test_post_message_to_unknown_thread_is_404(client: TestClient) -> None:
    response = client.post(f"/threads/{uuid.uuid4()}/messages", json={"question": "hi"})

    assert response.status_code == 404


def test_first_question_sets_thread_title(client: TestClient) -> None:
    created = client.post("/threads").json()
    thread_id = created["id"]

    client.post(f"/threads/{thread_id}/messages", json={"question": "How do refunds work?"})

    listed = client.get("/threads").json()
    assert listed[0]["title"] == "How do refunds work?"


def test_second_question_leaves_title_unchanged(client: TestClient) -> None:
    created = client.post("/threads").json()
    thread_id = created["id"]

    client.post(f"/threads/{thread_id}/messages", json={"question": "First question here"})
    title_after_first = client.get("/threads").json()[0]["title"]

    client.post(f"/threads/{thread_id}/messages", json={"question": "A completely different one"})
    title_after_second = client.get("/threads").json()[0]["title"]

    assert title_after_first == title_after_second == "First question here"


def test_generated_title_is_truncated_without_mid_word_break() -> None:
    long_question = "word " * 30
    title = derive_title(long_question)

    assert len(title) <= 60
    assert title.endswith("…")
    assert not title[:-1].endswith(" word"[1:])  # no dangling partial word before ellipsis


def test_rename_thread_persists_for_all_callers(client: TestClient) -> None:
    created = client.post("/threads").json()
    thread_id = created["id"]

    response = client.patch(f"/threads/{thread_id}", json={"title": "Renamed thread"})
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed thread"

    listed = client.get("/threads").json()
    assert listed[0]["title"] == "Renamed thread"


def test_rename_thread_with_blank_title_is_422_and_unchanged(client: TestClient) -> None:
    created = client.post("/threads").json()
    thread_id = created["id"]
    client.patch(f"/threads/{thread_id}", json={"title": "Original title"})

    response = client.patch(f"/threads/{thread_id}", json={"title": "   "})
    assert response.status_code == 422

    listed = client.get("/threads").json()
    assert listed[0]["title"] == "Original title"


def test_rename_unknown_thread_is_404(client: TestClient) -> None:
    response = client.patch(f"/threads/{uuid.uuid4()}", json={"title": "Anything"})

    assert response.status_code == 404


def test_delete_thread_cascades_and_is_gone(client: TestClient) -> None:
    created = client.post("/threads").json()
    thread_id = created["id"]
    client.post(f"/threads/{thread_id}/messages", json={"question": "hello"})

    response = client.delete(f"/threads/{thread_id}")
    assert response.status_code == 204

    assert client.get(f"/threads/{thread_id}").status_code == 404
    assert client.get("/threads").json() == []


def test_delete_unknown_thread_is_404(client: TestClient) -> None:
    response = client.delete(f"/threads/{uuid.uuid4()}")

    assert response.status_code == 404
