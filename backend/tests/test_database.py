"""Unit tests for `app/database.py`.

This ticket carries no acceptance criteria of its own -- `database.py` is
infrastructure (engine, session factory, the `get_db` dependency) with no
endpoint attached. These tests follow the contract documented in the
module's own docstring and comments instead: `DATABASE_URL` defaults to a
local SQLite file so a fresh clone runs with no database server, a SQLite
URL gets `check_same_thread=False` on its connect args (because FastAPI runs
sync dependencies in a threadpool) and no other backend does, `SessionLocal`
is built with `autoflush=False, expire_on_commit=False`, `Base` is a usable
`DeclarativeBase`, and `get_db` hands out one session per call and always
closes it -- including when the caller raises, which is exactly what
happens when a route handler errors mid-request.

Other suites (`conftest.py`'s `db_engine`/`db_session`/`client` fixtures, and
every test built on them) already exercise `Base` and `get_db` indirectly,
but always through an in-memory SQLite engine *of their own* construction,
never through `app.database`'s own `DATABASE_URL`-driven setup. This file
instead drives `app.database` itself -- directly for `Base`/`SessionLocal`/
`get_db`, and by reloading the module under different `DATABASE_URL` values
(the way `test_config.py` drives `app.config` directly) for the env-read
behaviour that only happens once, at import time, and so cannot be observed
by calling a function with different environments the way `app.config`'s
readers can.
"""

import importlib
import os

import pytest
from sqlalchemy.orm import DeclarativeBase, Session

from app import database


@pytest.fixture()
def _restore_database_module():
    """`DATABASE_URL`, `engine` and `_connect_args` in `app.database` are
    computed once at import time, not re-read per call -- so a test that
    reloads the module under a different `DATABASE_URL` leaves it in that
    state for the rest of the process unless something puts it back. Every
    other module in this app (`app.models`, `app.main`, every other test
    file) already did `from app.database import Base, engine, get_db` before
    this file ever runs and keeps its own reference to those *original*
    objects regardless of what this module reloads to later, but this suite
    itself reuses the plain `app.database` import across its own tests, so
    each reloading test restores the original `DATABASE_URL` (set or unset,
    whichever it was before the test ran) and reloads once more afterwards.
    """
    original_url = os.environ.get("DATABASE_URL")
    try:
        yield
    finally:
        if original_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = original_url
        importlib.reload(database)


# --- DATABASE_URL and the SQLite-only connect arg ---------------------------


def test_database_url_defaults_to_local_sqlite_file_when_unset(monkeypatch, _restore_database_module):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    reloaded = importlib.reload(database)

    assert reloaded.DATABASE_URL == "sqlite:///./app.db"


def test_database_url_reads_env_override(monkeypatch, _restore_database_module):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db/app")

    reloaded = importlib.reload(database)

    assert reloaded.DATABASE_URL == "postgresql+psycopg://user:pass@db/app"


def test_sqlite_database_url_gets_check_same_thread_false(monkeypatch, _restore_database_module):
    """SQLite rejects a connection used on a different thread than the one
    that opened it, which is exactly what happens when FastAPI runs a sync
    `get_db` dependency in its threadpool -- so any `sqlite:` URL, not just
    the default, must disable that check."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./some-other-file.db")

    reloaded = importlib.reload(database)

    assert reloaded._connect_args == {"check_same_thread": False}


def test_non_sqlite_database_url_gets_no_special_connect_args(monkeypatch, _restore_database_module):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@db/app")

    reloaded = importlib.reload(database)

    assert reloaded._connect_args == {}


def test_in_memory_sqlite_database_url_also_gets_check_same_thread_false(
    monkeypatch, _restore_database_module
):
    monkeypatch.setenv("DATABASE_URL", "sqlite://")

    reloaded = importlib.reload(database)

    assert reloaded._connect_args == {"check_same_thread": False}


# --- SessionLocal ------------------------------------------------------------


def test_session_local_builds_sessions_bound_to_the_module_engine() -> None:
    session = database.SessionLocal()
    try:
        assert isinstance(session, Session)
        assert session.get_bind() is database.engine
    finally:
        session.close()


def test_session_local_disables_autoflush_and_expiry_on_commit() -> None:
    """Required so that an object read before a commit (e.g. a document row
    a background task is updating) stays usable with the values it had at
    read time, instead of SQLAlchemy silently re-querying or flushing
    pending changes a caller did not ask for."""
    session = database.SessionLocal()
    try:
        assert session.autoflush is False
        assert session.expire_on_commit is False
    finally:
        session.close()


# --- Base --------------------------------------------------------------------


def test_base_is_a_declarative_base_every_model_can_subclass() -> None:
    assert issubclass(database.Base, DeclarativeBase)


def test_base_metadata_can_create_and_drop_tables_on_a_real_engine() -> None:
    """Exercises `Base.metadata` end to end against a throwaway engine of
    its own (not the shared `app.models` tables, which other suites already
    cover) -- a model declared against this `Base` must be a real,
    creatable table, not just a Python class."""
    from sqlalchemy import Column, Integer, String, create_engine

    class _Probe(database.Base):
        __tablename__ = "test_database_py_probe"
        id = Column(Integer, primary_key=True)
        name = Column(String)

    engine = create_engine("sqlite://")
    try:
        database.Base.metadata.create_all(bind=engine, tables=[_Probe.__table__])
        with engine.begin() as conn:
            conn.execute(_Probe.__table__.insert().values(id=1, name="a"))
            row = conn.execute(_Probe.__table__.select()).fetchone()
        assert row is not None
        assert row.name == "a"
    finally:
        database.Base.metadata.remove(_Probe.__table__)
        engine.dispose()


# --- get_db ------------------------------------------------------------------


class _FakeSession:
    """Stands in for a real `Session`, recording only whether `close()` was
    called -- `get_db` must close it exactly once per call, regardless of
    how the generator stops."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def test_get_db_yields_a_single_session(monkeypatch) -> None:
    fake_session = _FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: fake_session)

    generator = database.get_db()
    yielded = next(generator)

    assert yielded is fake_session
    generator.close()  # tidy up this test's own generator


def test_get_db_closes_the_session_once_the_caller_is_done(monkeypatch) -> None:
    fake_session = _FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: fake_session)

    generator = database.get_db()
    next(generator)
    assert fake_session.closed is False

    with pytest.raises(StopIteration):
        next(generator)

    assert fake_session.closed is True


def test_get_db_closes_the_session_even_when_the_caller_raises(monkeypatch) -> None:
    """Mirrors what actually happens in production: FastAPI resumes the
    `get_db` generator by throwing the route handler's exception back into
    it at the `yield` point, and `get_db`'s `finally` must still close the
    session rather than leaking the connection."""
    fake_session = _FakeSession()
    monkeypatch.setattr(database, "SessionLocal", lambda: fake_session)

    generator = database.get_db()
    next(generator)

    with pytest.raises(ValueError):
        generator.throw(ValueError("handler blew up"))

    assert fake_session.closed is True


def test_get_db_gives_each_call_its_own_session() -> None:
    first = next(database.get_db())
    second = next(database.get_db())

    try:
        assert first is not second
    finally:
        first.close()
        second.close()
