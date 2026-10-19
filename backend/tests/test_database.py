"""Unit tests for `app.database`: the engine/session factory configuration
and the `get_db` request-scoped session dependency.

`conftest.py`'s `client`/`db_session`/`db_engine` fixtures already exercise
`get_db`'s happy path end to end through every route in the API (by
overriding it with their own in-memory engine), so this file does not
repeat that. Instead it covers what no other suite reaches directly: that
`get_db` actually closes its session on every exit, success or exception
alike, that the SQLite/non-SQLite branch in `_connect_args` picks the
documented value either way, that `SessionLocal` is built with the
`autoflush`/`expire_on_commit` settings the module's own docstring and
comments promise, that `Base` is the declarative base the generated models
actually register themselves on, and -- unmocked, against the real default
engine `get_db` is wired to in `main.py` -- that a real request really can
open and close a session through it.
"""

import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import database as database_module
from app import models  # noqa: F401 -- registers the generated tables on Base
from app.database import Base, SessionLocal, get_db
from app.main import app

# --- get_db: a session every call, closed on every exit ---------------------


class _FakeSession:
    """Stands in for a real `Session`; `get_db`'s contract under test is
    "close exactly once, on the way out" -- not which database the session
    it hands back is wired to."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_get_db_yields_a_session_and_closes_it_once_the_caller_is_done(monkeypatch) -> None:
    fake_session = _FakeSession()
    monkeypatch.setattr(database_module, "SessionLocal", lambda: fake_session)

    gen = database_module.get_db()
    yielded = next(gen)

    assert yielded is fake_session
    assert fake_session.closed is False

    with pytest.raises(StopIteration):
        next(gen)
    assert fake_session.closed is True


def test_get_db_closes_the_session_even_when_the_caller_raises(monkeypatch) -> None:
    """FastAPI drives this generator with `.throw(...)` when the handler it
    wraps raises, exactly as a broken request handler would -- the `finally`
    in `get_db` has to run (and close the session) on that path too, not
    only on the clean one, or a session leaks every time a request fails."""
    fake_session = _FakeSession()
    monkeypatch.setattr(database_module, "SessionLocal", lambda: fake_session)

    gen = database_module.get_db()
    next(gen)

    with pytest.raises(ValueError, match="handler blew up"):
        gen.throw(ValueError("handler blew up"))
    assert fake_session.closed is True


def test_get_db_yields_a_real_sqlalchemy_session() -> None:
    gen = get_db()
    session = next(gen)
    try:
        assert isinstance(session, Session)
    finally:
        gen.close()


# --- SessionLocal: autoflush and expire-on-commit are both disabled --------


def test_session_local_sessions_have_autoflush_and_expire_on_commit_disabled() -> None:
    """Both are load-bearing, not incidental: `expire_on_commit=False` is
    what lets a route return the ORM object it just committed (e.g.
    `create_thread`, `upload_documents`) without a second round trip to
    refresh it, and `autoflush=False` keeps a read made mid-handler from
    implicitly flushing an unfinished write."""
    session = SessionLocal()
    try:
        assert session.autoflush is False
        assert session.expire_on_commit is False
    finally:
        session.close()


# --- Base: the declarative base the generated models actually use ----------


def test_base_metadata_registers_every_generated_table() -> None:
    """Proves `Base` is not merely importable but is the exact base class
    `app.models` declares its tables against -- `app.models` is imported at
    the top of this file for precisely that side effect."""
    table_names = set(Base.metadata.tables)

    assert {"documents", "chunks", "threads", "messages", "citations"} <= table_names


# --- DATABASE_URL / _connect_args: the SQLite-vs-everything-else branch ----


@pytest.fixture()
def _restore_database_module():
    """`DATABASE_URL`, `_connect_args`, `engine` and `SessionLocal` are all
    computed once at import time, so the only way to exercise either branch
    of the module's own `if DATABASE_URL.startswith("sqlite")` is to reload
    it under a controlled environment -- restored here, by reloading again
    with `DATABASE_URL` unset, so this module is left exactly as every other
    test in the suite (and `app.main`, imported long before this file ever
    runs) expects it: pointed at the local SQLite default.

    This never touches `app.main`'s own already-imported `engine`/`get_db`
    references (bound once, at `app.main`'s own import, long before this
    fixture runs) or `app.models`'s already-defined `Base` subclasses, so it
    cannot affect any other test in this suite.
    """
    yield
    import os

    os.environ.pop("DATABASE_URL", None)
    importlib.reload(database_module)


def test_default_database_url_is_local_sqlite_and_sets_check_same_thread(
    monkeypatch, _restore_database_module
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    importlib.reload(database_module)

    assert database_module.DATABASE_URL == "sqlite:///./app.db"
    assert database_module._connect_args == {"check_same_thread": False}


def test_non_sqlite_database_url_omits_check_same_thread(
    monkeypatch, _restore_database_module
) -> None:
    """SQLite's `check_same_thread` is not a keyword a real database driver
    understands; passing it to one would raise, not merely be ignored, so
    the branch that omits it for a non-SQLite `DATABASE_URL` is load-bearing
    on its own, not just the SQLite branch's complement."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")

    importlib.reload(database_module)

    assert database_module._connect_args == {}
    assert database_module.engine.dialect.name == "postgresql"


# --- get_db, unmocked: a real request really opens and closes a session ---


def test_get_db_is_wired_into_a_real_route_against_the_real_default_engine() -> None:
    """Every other suite overrides `get_db` with its own in-memory database
    (see `conftest.py`), which proves the override seam works but never
    proves `get_db` itself -- unmocked, undone -- is actually what `app.main`
    wires every route to. This hits `POST /threads` through a fresh
    `TestClient` with no override installed, so it runs against the module's
    real default engine end to end, then deletes what it created so this
    suite leaves no state behind for a later test to trip over."""
    real_client = TestClient(app)

    response = real_client.post("/threads")
    assert response.status_code == 200
    thread_id = response.json()["id"]

    listed_ids = {t["id"] for t in real_client.get("/threads").json()}
    assert thread_id in listed_ids

    cleanup = real_client.delete(f"/threads/{thread_id}")
    assert cleanup.status_code == 204
