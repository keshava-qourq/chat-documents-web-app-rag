"""Per-IP rate limiting on chat and upload (US-019 / AC-064).

Uses the shared `client`, `db_session` and `fake_object_store` fixtures from
`conftest.py` for an in-memory SQLite database and a fake object store in
place of MinIO. `app.routers.threads.request_answer` -- the seam that will
eventually call Gemini -- is monkeypatched to a spy in every chat test, so
this suite never makes a real Gemini call, and `fake_object_store` already
keeps uploads off real MinIO. No test sleeps: the "window elapses" scenario
is proven by driving the limiter's own storage via `limiter.reset()`, not by
waiting for real time to pass.

The module-level `_generous_rate_limits` fixture in conftest.py sets both
limit env vars sky-high so every *other* suite in this repo never trips a
429 by accident. Every test here overrides those env vars back down to a
small, test-specific number (or removes them to exercise the real default)
and resets the limiter's storage before and after itself, so none of these
tests can leak a counted request into another test, in this file or any
other, regardless of run order.
"""

import pytest
from fastapi.testclient import TestClient

from app.config import (
    RATE_LIMIT_CHAT_PER_MIN_DEFAULT,
    RATE_LIMIT_UPLOADS_PER_HOUR_DEFAULT,
)
from app.main import app
from app.models import Document
from app.rate_limit import RATE_LIMIT_MESSAGE, limiter
from app.routers import threads as threads_router

TXT_BYTES = b"plain text content"


def _file(name: str):
    return ("files", (name, TXT_BYTES, "text/plain"))


@pytest.fixture(autouse=True)
def _reset_limiter_state():
    """Clears every IP's counted requests before and after each test, so a
    bucket filled by one test (or by a previous run of this module) can
    never be mistaken for one filled by the test currently running."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture()
def request_answer_spy(monkeypatch):
    calls: list[tuple[str, list[dict[str, str]]]] = []

    def fake_request_answer(question, context):
        calls.append((question, context))
        return None

    monkeypatch.setattr(threads_router, "request_answer", fake_request_answer)
    return calls


# --- chat: exceeding the limit returns 429 and never reaches the seam ------


def test_exceeding_chat_limit_returns_429_and_never_invokes_generation_seam(
    client, monkeypatch, request_answer_spy
) -> None:
    monkeypatch.setenv("RATE_LIMIT_CHAT_PER_MIN", "3")
    thread_id = client.post("/threads").json()["id"]

    for i in range(3):
        response = client.post(f"/threads/{thread_id}/messages", json={"question": f"q{i}"})
        assert response.status_code == 200

    rejected = client.post(f"/threads/{thread_id}/messages", json={"question": "one too many"})

    assert rejected.status_code == 429
    assert rejected.json() == {"detail": RATE_LIMIT_MESSAGE}
    # Three accepted requests reached the seam; the rejected fourth did not.
    assert len(request_answer_spy) == 3
    assert "one too many" not in {q for q, _ in request_answer_spy}


# --- upload: exceeding the limit returns 429 and stores/persists nothing --


def test_exceeding_upload_limit_returns_429_and_persists_nothing_for_rejected_request(
    client, db_session, fake_object_store, monkeypatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_HOUR", "2")

    for i in range(2):
        response = client.post("/documents", files=[_file(f"ok{i}.txt")])
        assert response.status_code == 200
        assert response.json()["accepted"][0]["file_name"] == f"ok{i}.txt"

    rejected = client.post("/documents", files=[_file("never-uploaded.txt")])

    assert rejected.status_code == 429
    assert rejected.json() == {"detail": RATE_LIMIT_MESSAGE}
    assert (
        db_session.query(Document).filter(Document.file_name == "never-uploaded.txt").count() == 0
    )
    assert all(key != "never-uploaded.txt" for key in fake_object_store)
    assert len(fake_object_store) == 2  # only the two accepted uploads were ever stored


# --- requests succeed again once the limiter's window has elapsed ---------


def test_chat_requests_succeed_again_after_the_limiter_window_elapses(
    client, monkeypatch, request_answer_spy
) -> None:
    monkeypatch.setenv("RATE_LIMIT_CHAT_PER_MIN", "1")
    thread_id = client.post("/threads").json()["id"]

    first = client.post(f"/threads/{thread_id}/messages", json={"question": "first"})
    assert first.status_code == 200

    blocked = client.post(f"/threads/{thread_id}/messages", json={"question": "blocked"})
    assert blocked.status_code == 429

    # Drive the limiter's own storage rather than sleeping in real time: a
    # cleared bucket is exactly what a caller sees once their window has
    # rolled over.
    limiter.reset()

    after_window = client.post(
        f"/threads/{thread_id}/messages", json={"question": "after window"}
    )
    assert after_window.status_code == 200
    assert len(request_answer_spy) == 2  # "first" and "after window", not "blocked"


def test_upload_requests_succeed_again_after_the_limiter_window_elapses(
    client, fake_object_store, monkeypatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_HOUR", "1")

    first = client.post("/documents", files=[_file("first.txt")])
    assert first.status_code == 200

    blocked = client.post("/documents", files=[_file("blocked.txt")])
    assert blocked.status_code == 429

    limiter.reset()

    after_window = client.post("/documents", files=[_file("after-window.txt")])
    assert after_window.status_code == 200
    assert after_window.json()["accepted"][0]["file_name"] == "after-window.txt"


# --- limits are read from the documented env vars, with documented defaults -


def test_chat_limit_is_read_from_rate_limit_chat_per_min_env_var(
    client, monkeypatch, request_answer_spy
) -> None:
    monkeypatch.setenv("RATE_LIMIT_CHAT_PER_MIN", "2")
    thread_id = client.post("/threads").json()["id"]

    assert client.post(f"/threads/{thread_id}/messages", json={"question": "a"}).status_code == 200
    assert client.post(f"/threads/{thread_id}/messages", json={"question": "b"}).status_code == 200
    assert client.post(f"/threads/{thread_id}/messages", json={"question": "c"}).status_code == 429


def test_upload_limit_is_read_from_rate_limit_uploads_per_hour_env_var(
    client, monkeypatch
) -> None:
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_HOUR", "1")

    assert client.post("/documents", files=[_file("one.txt")]).status_code == 200
    assert client.post("/documents", files=[_file("two.txt")]).status_code == 429


def test_typical_chat_traffic_under_the_default_chat_limit_all_stay_200(
    client, monkeypatch, request_answer_spy
) -> None:
    monkeypatch.delenv("RATE_LIMIT_CHAT_PER_MIN", raising=False)
    thread_id = client.post("/threads").json()["id"]

    under_default = RATE_LIMIT_CHAT_PER_MIN_DEFAULT - 1
    for i in range(under_default):
        response = client.post(f"/threads/{thread_id}/messages", json={"question": f"q{i}"})
        assert response.status_code == 200
    assert len(request_answer_spy) == under_default


def test_typical_upload_traffic_under_the_default_upload_limit_all_stay_200(
    client, fake_object_store, monkeypatch
) -> None:
    monkeypatch.delenv("RATE_LIMIT_UPLOADS_PER_HOUR", raising=False)

    under_default = RATE_LIMIT_UPLOADS_PER_HOUR_DEFAULT - 1
    for i in range(under_default):
        response = client.post("/documents", files=[_file(f"doc{i}.txt")])
        assert response.status_code == 200
    assert len(fake_object_store) == under_default


# --- different client IPs are rate limited independently ------------------


def test_different_client_ips_are_rate_limited_independently(
    client, fake_object_store, monkeypatch
) -> None:
    """Relies on starlette's TestClient `client=(host, port)` constructor
    argument to give each simulated caller a distinct `request.client.host`
    -- the value slowapi's default key function keys buckets on -- while
    both test clients share the one `app` object (and therefore the one
    `get_db` override the `client` fixture already installed, and the one
    patched `app.storage`), so no extra setup is needed beyond this test's
    own two TestClient instances.
    """
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_HOUR", "1")

    ip_a = TestClient(app, client=("10.0.0.1", 12345))
    ip_b = TestClient(app, client=("10.0.0.2", 12345))

    assert ip_a.post("/documents", files=[_file("a1.txt")]).status_code == 200
    assert ip_a.post("/documents", files=[_file("a2.txt")]).status_code == 429

    # A fresh IP still has its own, untouched bucket.
    assert ip_b.post("/documents", files=[_file("b1.txt")]).status_code == 200
