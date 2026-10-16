"""Unit tests for `app.database`.

`conftest.py`'s fixtures already exercise `get_db`/`Base`/`engine`
*indirectly* through the `client` fixture -- every request in every other
suite runs through a session this module hands out. What none of that
proves: what `DATABASE_URL` defaults to and that it is actually read from
the environment, that the SQLite-only `check_same_thread` workaround applies
to a SQLite URL and nothing else, that the session factory is configured the
way the module claims (`autoflush=False`, `expire_on_commit=False`, bound to
this module's own engine), and the module's one behavioural promise --
`get_db`'s docstring says a session is "closed even when the handler
raises" -- which no other suite has a reason to go looking for, since every
other suite's handlers succeed.

`DATABASE_URL` and the SQLite-only `connect_args` are computed once at
import time (unlike `app.config`, which reads `os.environ` fresh on every
call), so the tests that vary `DATABASE_URL` cannot just call a function
with a patched environment. They also must not `importlib.reload` the real
`app.database` module in place: that would rebuild `Base` as a brand-new
class object, which would silently break `issubclass(Document, Base)` (and
everything else keyed on that one `Base`/`engine`/`get_db` identity) for
every test that runs afterwards in this process -- `app.main` and
`conftest.py` already bound their own references to the *original* objects
at collection time and would never see the replacement. Instead,
`_load_fresh_database_module` executes `database.py`'s source into an
independent module object that is never registered in `sys.modules`, so the
one the rest of the application already uses is never touched.
"""

import importlib.util

import pytest
from sqlalchemy.orm import DeclarativeBase, Session

from app import database as database_module
from app.models import Document


def _load_fresh_database_module():
    """A brand-new execution of `database.py`, independent of (and never
    substituted for) `sys.modules["app.database"]`, so DATABASE_URL and the
    SQLite-only connect_args can be observed under a patched environment
    without disturbing the module instance everything else in the process
    already imported from."""
    spec = importlib.util.spec_from_file_location(
        "app_database_fresh_copy_for_tests", database_module.__file__
    )
    fresh_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh_module)
    return fresh_module


# --- DATABASE_URL: documented default and env override ----------------------


def test_database_url_defaults_to_local_sqlite_file_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    fresh = _load_fresh_database_module()

    assert fresh.DATABASE_URL == "sqlite:///./app.db"


def test_database_url_is_read_from_its_env_var(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
    fresh = _load_fresh_database_module()

    assert fresh.DATABASE_URL == "postgresql+psycopg://user:pass@localhost/db"


# --- connect_args: only a sqlite URL gets check_same_thread=False -----------


def test_sqlite_url_gets_check_same_thread_false_connect_arg(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./somewhere-else.db")
    fresh = _load_fresh_database_module()

    assert fresh._connect_args == {"check_same_thread": False}
    assert fresh.engine.dialect.name == "sqlite"


def test_non_sqlite_url_gets_no_special_connect_args(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:pass@localhost/db")
    fresh = _load_fresh_database_module()

    assert fresh._connect_args == {}
    assert fresh.engine.dialect.name == "postgresql"


def test_in_memory_sqlite_url_still_gets_check_same_thread_false(monkeypatch) -> None:
    # Guards against a narrower fix that only matches the on-disk
    # `sqlite:///` form: any URL starting with "sqlite" needs the same
    # workaround, in-memory included.
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    fresh = _load_fresh_database_module()

    assert fresh._connect_args == {"check_same_thread": False}


# --- SessionLocal: configured the way the module claims ---------------------


def test_session_factory_is_bound_to_the_module_engine() -> None:
    assert database_module.SessionLocal.kw["bind"] is database_module.engine


def test_session_factory_disables_autoflush_and_does_not_expire_on_commit() -> None:
    # Documented by name in the module: a session must not be expired on
    # commit, or a second, independent session reading through a different
    # identity map would stop seeing what the first one just wrote.
    assert database_module.SessionLocal.kw["autoflush"] is False
    assert database_module.SessionLocal.kw["expire_on_commit"] is False


def test_session_local_produces_real_sqlalchemy_sessions() -> None:
    session = database_module.SessionLocal()
    try:
        assert isinstance(session, Session)
        assert session.bind is database_module.engine
    finally:
        session.close()


# --- Base: the one declarative base every model inherits --------------------


def test_base_is_a_declarative_base_every_model_inherits() -> None:
    assert issubclass(database_module.Base, DeclarativeBase)
    assert issubclass(Document, database_module.Base)


# --- get_db: yields one session, closes it in every case --------------------


def test_get_db_yields_a_single_usable_session() -> None:
    generator = database_module.get_db()
    try:
        session = next(generator)
        assert isinstance(session, Session)
    finally:
        generator.close()


def test_get_db_closes_its_session_once_the_caller_is_done_with_it(monkeypatch) -> None:
    closed = {"value": False}

    class _FakeSession:
        def close(self) -> None:
            closed["value"] = True

    monkeypatch.setattr(database_module, "SessionLocal", lambda: _FakeSession())

    generator = database_module.get_db()
    next(generator)
    # Mirrors what FastAPI does once the request handler returns normally:
    # it drives the generator past its `yield`, which must still run the
    # `finally` block below that yield -- not only the exception path.
    generator.close()

    assert closed["value"] is True


def test_get_db_closes_its_session_even_when_the_handler_raises(monkeypatch) -> None:
    closed = {"value": False}

    class _FakeSession:
        def close(self) -> None:
            closed["value"] = True

    monkeypatch.setattr(database_module, "SessionLocal", lambda: _FakeSession())

    generator = database_module.get_db()
    next(generator)

    with pytest.raises(RuntimeError, match="boom"):
        generator.throw(RuntimeError("boom"))

    # The documented promise this function makes: a session is closed even
    # when the handler using it raises, not only on the happy path.
    assert closed["value"] is True


def test_get_db_yields_a_fresh_session_on_every_call(monkeypatch) -> None:
    created = []

    class _FakeSession:
        def close(self) -> None:
            pass

    def _fake_session_local():
        session = _FakeSession()
        created.append(session)
        return session

    monkeypatch.setattr(database_module, "SessionLocal", _fake_session_local)

    first_generator = database_module.get_db()
    first_session = next(first_generator)
    first_generator.close()

    second_generator = database_module.get_db()
    second_session = next(second_generator)
    second_generator.close()

    # One session per request, not one shared across requests.
    assert first_session is not second_session
    assert len(created) == 2
