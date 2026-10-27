"""Behavioural tests for the threads API: shared listing, creation,
auto-titling, rename validation and cascading delete.

Uses the shared `client`, `db_session` and `db_sessionmaker` fixtures from
`conftest.py` -- an in-memory SQLite database per test, no live Gemini or
MinIO call anywhere in this module, and no wall-clock sleeps: ordering is
proven by writing distinct `last_active_at` values directly, not by waiting
for time to pass.
"""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app import embeddings
from app.database import get_db
from app.main import app
from app.models import Chunk, Citation, Document, Message, Thread
from app.services import derive_title

# --- AC-043: empty list -------------------------------------------------


def test_list_threads_returns_empty_list_when_there_are_none(client) -> None:
    response = client.get("/threads")

    assert response.status_code == 200
    assert response.json() == []


# --- AC-041: ordering by last_active_at desc ----------------------------


def test_list_threads_orders_by_last_active_at_descending(client, db_session) -> None:
    oldest = client.post("/threads").json()["id"]
    middle = client.post("/threads").json()["id"]
    newest = client.post("/threads").json()["id"]

    base = datetime(2026, 1, 1, tzinfo=UTC)
    for thread_id, offset in ((oldest, 0), (middle, 1), (newest, 2)):
        db_session.query(Thread).filter(Thread.id == uuid.UUID(thread_id)).update(
            {"last_active_at": base + timedelta(hours=offset)}
        )
    db_session.commit()

    response = client.get("/threads")

    assert response.status_code == 200
    ordered_ids = [item["id"] for item in response.json()]
    assert ordered_ids == [newest, middle, oldest]


# --- posting a message bumps the thread's own last_active_at -------------


def test_posting_a_message_moves_its_thread_to_the_top_of_the_list(client) -> None:
    """Unlike the test above (which writes `last_active_at` directly to
    prove ordering itself), this drives the real behaviour end to end: the
    router bumps `last_active_at` to the current time whenever a question is
    posted, so an older thread that gets a new question jumps back above a
    thread nobody has touched since -- without needing to assert anything
    about the untouched thread's own position, which creation order alone
    does not guarantee on a database with second-level timestamp
    resolution.
    """
    older = client.post("/threads").json()["id"]
    client.post("/threads")  # a second, untouched thread

    client.post(f"/threads/{older}/messages", json={"question": "Wake this thread back up"})

    reordered = [item["id"] for item in client.get("/threads").json()]
    assert reordered[0] == older


# --- AC-042: identical bodies for different callers ---------------------


def test_list_threads_is_identical_for_different_callers(client) -> None:
    client.post("/threads")

    response_a = client.get("/threads", headers={"User-Agent": "caller-a"})
    response_b = client.get("/threads", headers={"User-Agent": "caller-b"})

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    assert response_a.json() == response_b.json()


# --- AC-044 / AC-045: create then fetch ----------------------------------


def test_create_thread_then_get_it_returns_an_empty_new_conversation(client) -> None:
    create_response = client.post("/threads")

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["title"] == "New conversation"
    assert "id" in created
    assert "created_at" in created

    get_response = client.get(f"/threads/{created['id']}")

    assert get_response.status_code == 200
    body = get_response.json()
    assert body["id"] == created["id"]
    assert body["title"] == "New conversation"
    assert body["messages"] == []


def test_get_unknown_thread_id_returns_404(client) -> None:
    response = client.get(f"/threads/{uuid.uuid4()}")

    assert response.status_code == 404


# --- GET returns every turn, in the order it was asked --------------------


def test_get_thread_returns_every_question_in_chronological_order(client) -> None:
    thread_id = client.post("/threads").json()["id"]

    client.post(f"/threads/{thread_id}/messages", json={"question": "First question"})
    client.post(f"/threads/{thread_id}/messages", json={"question": "Second question"})
    client.post(f"/threads/{thread_id}/messages", json={"question": "Third question"})

    detail = client.get(f"/threads/{thread_id}").json()
    user_messages = [m for m in detail["messages"] if m["role"] == "user"]
    assert [m["content"] for m in user_messages] == [
        "First question",
        "Second question",
        "Third question",
    ]
    for message in user_messages:
        assert message["role"] == "user"
        assert message["citations"] == []


# --- posting a question against an unknown thread -------------------------


def test_post_message_to_unknown_thread_id_returns_404(client) -> None:
    response = client.post(f"/threads/{uuid.uuid4()}/messages", json={"question": "hi"})

    assert response.status_code == 404


# --- AC-048 / AC-049 / AC-050: auto-titling ------------------------------


def test_first_question_sets_a_derived_title(client) -> None:
    thread_id = client.post("/threads").json()["id"]
    question = "What is the per diem for staff travelling to the Berlin office?"

    message_response = client.post(f"/threads/{thread_id}/messages", json={"question": question})
    assert message_response.status_code == 200

    thread = client.get(f"/threads/{thread_id}").json()
    assert thread["title"] == derive_title(question)
    assert thread["title"] != "New conversation"


def test_a_very_long_first_question_yields_a_title_truncated_to_60_chars(client) -> None:
    thread_id = client.post("/threads").json()["id"]
    question = " ".join(["supercalifragilisticexpialidocious"] * 10)

    client.post(f"/threads/{thread_id}/messages", json={"question": question})

    thread = client.get(f"/threads/{thread_id}").json()
    assert len(thread["title"]) <= 60
    assert thread["title"] == derive_title(question)


def test_a_second_question_leaves_the_title_unchanged(client) -> None:
    thread_id = client.post("/threads").json()["id"]
    first_question = "How much parental leave top-up do Dutch staff get?"
    client.post(f"/threads/{thread_id}/messages", json={"question": first_question})
    title_after_first = client.get(f"/threads/{thread_id}").json()["title"]

    client.post(
        f"/threads/{thread_id}/messages",
        json={"question": "And what about staff based in Berlin instead?"},
    )

    title_after_second = client.get(f"/threads/{thread_id}").json()["title"]
    assert title_after_second == title_after_first


# --- AC-051 / AC-052: rename ---------------------------------------------


def test_rename_stores_and_returns_the_new_title_for_every_caller(client) -> None:
    thread_id = client.post("/threads").json()["id"]

    rename_response = client.patch(
        f"/threads/{thread_id}", json={"title": "Office holidays policy"}
    )

    assert rename_response.status_code == 200
    body = rename_response.json()
    assert body["id"] == thread_id
    assert body["title"] == "Office holidays policy"

    for user_agent in ("caller-a", "caller-b"):
        listed = client.get("/threads", headers={"User-Agent": user_agent}).json()
        matching = next(item for item in listed if item["id"] == thread_id)
        assert matching["title"] == "Office holidays policy"


def test_rename_with_empty_title_returns_422_and_leaves_previous_title_intact(client) -> None:
    thread_id = client.post("/threads").json()["id"]

    response = client.patch(f"/threads/{thread_id}", json={"title": "   "})

    assert response.status_code == 422

    thread = client.get(f"/threads/{thread_id}").json()
    assert thread["title"] == "New conversation"


def test_rename_unknown_thread_id_returns_404(client) -> None:
    response = client.patch(f"/threads/{uuid.uuid4()}", json={"title": "Anything"})

    assert response.status_code == 404


# --- AC-053: cascading delete --------------------------------------------


def test_delete_returns_204_and_removes_all_messages_and_citations(client, db_session) -> None:
    thread_id = client.post("/threads").json()["id"]
    client.post(
        f"/threads/{thread_id}/messages", json={"question": "Where is the expenses policy?"}
    )
    # The streamed response body is SSE, not JSON, so the user message's id
    # is read directly from the database this thread was persisted to,
    # rather than parsed off the response -- the same place a second client
    # instance would have to look it up from too.
    message = (
        db_session.query(Message)
        .filter(Message.thread_id == uuid.UUID(thread_id), Message.role == "user")
        .one()
    )
    db_session.add(
        Citation(
            id=uuid.uuid4(),
            message_id=message.id,
            chunk_id=None,
            document_name="handbook.pdf",
            source_location="p.3",
            excerpt="Expenses must be submitted within 30 days.",
        )
    )
    db_session.commit()

    delete_response = client.delete(f"/threads/{thread_id}")

    assert delete_response.status_code == 204
    assert delete_response.content in (b"", None)

    assert db_session.query(Message).filter(Message.thread_id == uuid.UUID(thread_id)).count() == 0
    assert db_session.query(Citation).count() == 0
    assert client.get(f"/threads/{thread_id}").status_code == 404


def test_delete_unknown_thread_id_returns_404(client) -> None:
    response = client.delete(f"/threads/{uuid.uuid4()}")

    assert response.status_code == 404


# --- no authentication anywhere on this surface --------------------------


def test_no_thread_route_returns_401_or_403_for_an_unauthenticated_caller(client) -> None:
    created = client.post("/threads")
    assert created.status_code not in (401, 403)
    thread_id = created.json()["id"]

    assert client.get("/threads").status_code not in (401, 403)
    assert client.get(f"/threads/{thread_id}").status_code not in (401, 403)
    assert client.post(
        f"/threads/{thread_id}/messages", json={"question": "Anything?"}
    ).status_code not in (401, 403)
    assert client.patch(f"/threads/{thread_id}", json={"title": "Renamed"}).status_code not in (
        401,
        403,
    )
    assert client.delete(f"/threads/{thread_id}").status_code not in (401, 403)


# --- AC-047: server-side persistence across client instances -------------


def test_a_second_client_instance_over_the_same_database_reconstructs_the_thread(
    db_sessionmaker, fake_object_store
) -> None:
    """Proves persistence lives in the database, not in any in-process state
    the first client happened to hold: a brand new `TestClient` (standing in
    for a second browser tab or a server restart) sees the same thread and
    message through a completely fresh app lifecycle."""

    def override_get_db():
        session = db_sessionmaker()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as first_client:
            created = first_client.post("/threads").json()
            thread_id = created["id"]
            first_client.post(
                f"/threads/{thread_id}/messages",
                json={"question": "Where is the remote work policy documented?"},
            )

        with TestClient(app) as second_client:
            response = second_client.get(f"/threads/{thread_id}")
            assert response.status_code == 200
            body = response.json()
            assert body["id"] == thread_id
            assert len(body["messages"]) == 1
            assert body["messages"][0]["content"] == "Where is the remote work policy documented?"
    finally:
        app.dependency_overrides.pop(get_db, None)


# --- AC-067: chat pre-flight check for a missing GEMINI_API_KEY -----------
#
# `app.services.request_answer` itself only calls Gemini once a `'ready'`
# document exists (otherwise it returns its own canned, Gemini-free reply),
# so `post_message` checks for a configured key *before* persisting
# anything, and only when a `'ready'` document actually exists to answer
# from. Both branches of that pre-flight live here, next to the rest of this
# router's behaviour, exercised through the same `client` / `db_session`
# fixtures as every other test in this module -- no real Gemini call is
# reachable either way.


def _seed_ready_document_with_chunk(db_session) -> Document:
    document = Document(
        id=uuid.uuid4(),
        file_name="handbook.pdf",
        mime_type="application/pdf",
        size_bytes=10,
        storage_key="handbook.pdf",
        status="ready",
        chunk_count=1,
    )
    db_session.add(document)
    db_session.commit()
    chunk = Chunk(
        id=uuid.uuid4(),
        document_id=document.id,
        content="Employees get 25 days of annual leave.",
        source_location="handbook.pdf, page 1",
        chunk_index=0,
        embedding=[1.0, 0.0],
    )
    db_session.add(chunk)
    db_session.commit()
    return document


def test_chat_returns_structured_503_when_gemini_is_not_configured_and_a_document_is_ready(
    client, db_session, monkeypatch
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    _seed_ready_document_with_chunk(db_session)

    def fail_if_called(*args, **kwargs):
        raise AssertionError("Gemini must not be called when GEMINI_API_KEY is unset")

    monkeypatch.setattr(embeddings, "embed_texts", fail_if_called)

    thread_id = client.post("/threads").json()["id"]
    response = client.post(f"/threads/{thread_id}/messages", json={"question": "How many days?"})

    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["code"] == "gemini_not_configured"
    assert "GEMINI_API_KEY" in body["detail"]["message"]

    # The pre-flight check runs before anything is written to the thread --
    # not even the user's own question was persisted.
    detail = client.get(f"/threads/{thread_id}").json()
    assert detail["messages"] == []


def test_chat_still_answers_without_a_gemini_key_when_no_document_is_ready(
    client, monkeypatch
) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    thread_id = client.post("/threads").json()["id"]
    response = client.post(f"/threads/{thread_id}/messages", json={"question": "Anything?"})

    # No ready documents yet -> `request_answer`'s own canned, Gemini-free
    # reply applies; a missing key must not block this case, and the user's
    # question is still persisted.
    assert response.status_code == 200
    detail = client.get(f"/threads/{thread_id}").json()
    assert detail["messages"][0]["content"] == "Anything?"
