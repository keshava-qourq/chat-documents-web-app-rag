"""Unit tests for the exception handlers `app.main` registers for
`GeminiNotConfiguredError` / `GeminiKeyRejectedError`, from each of
`app.embeddings` and `app.generation`.

Every current caller of these four exception types already catches its own
before it could ever reach FastAPI's exception-handling middleware:
`app.ingestion` catches both of `app.embeddings`'s during background
indexing, and `app.services.request_answer` catches both of
`app.generation`'s and turns them into an SSE event instead of letting them
propagate (see `app/tests/test_gemini_config_error.py`, which proves that
503 comes from a plain `HTTPException` the chat endpoint raises itself, not
from either handler registered here). So nothing anywhere in this suite
actually exercises `main.py`'s own `app.add_exception_handler(...)`
registrations -- this file is that coverage, raising each of the four
registered types from inside a `get_db` dependency override (the same
dependency-substitution pattern `conftest.py`'s own `client` fixture already
uses) so the response comes from the real handler wired to the real `app`,
not from a copy of its logic.

Uses the `client` fixture from `conftest.py` and then replaces its
`get_db` override with one that raises instead of yielding a session; the
fixture's own teardown pops whatever is left in `app.dependency_overrides`,
so this leaves nothing behind for the next test.
"""

from app import embeddings, generation
from app.database import get_db
from app.main import app


def _raising_dependency(exc: Exception):
    """A `get_db`-shaped dependency that raises `exc` before ever yielding a
    session -- a generator function (it contains `yield`), so FastAPI only
    raises when it actually opens the dependency for a request, not when
    this factory is called."""

    def _gen():
        raise exc
        yield  # pragma: no cover -- never reached; this must stay a generator

    return _gen


# --- app.embeddings' errors -------------------------------------------------


def test_embeddings_not_configured_error_becomes_a_structured_503(client) -> None:
    app.dependency_overrides[get_db] = _raising_dependency(
        embeddings.GeminiNotConfiguredError("GEMINI_API_KEY is not configured")
    )

    response = client.get("/threads")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "gemini_not_configured",
            "message": "GEMINI_API_KEY is not configured",
        }
    }


def test_embeddings_key_rejected_error_becomes_a_structured_503_naming_the_status(client) -> None:
    app.dependency_overrides[get_db] = _raising_dependency(
        embeddings.GeminiKeyRejectedError(
            "GEMINI_API_KEY was rejected by Gemini (status 401)", status_code=401
        )
    )

    response = client.get("/threads")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "gemini_key_rejected",
            "message": "GEMINI_API_KEY was rejected by Gemini (status 401)",
        }
    }


# --- app.generation's errors -------------------------------------------------


def test_generation_not_configured_error_becomes_a_structured_503(client) -> None:
    app.dependency_overrides[get_db] = _raising_dependency(
        generation.GeminiNotConfiguredError("GEMINI_API_KEY is not configured")
    )

    response = client.get("/threads")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "gemini_not_configured",
            "message": "GEMINI_API_KEY is not configured",
        }
    }


def test_generation_key_rejected_error_becomes_a_structured_503_naming_the_status(client) -> None:
    app.dependency_overrides[get_db] = _raising_dependency(
        generation.GeminiKeyRejectedError(
            "GEMINI_API_KEY was rejected by Gemini (status 403)", status_code=403
        )
    )

    response = client.get("/threads")

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "gemini_key_rejected",
            "message": "GEMINI_API_KEY was rejected by Gemini (status 403)",
        }
    }


# --- the key value itself never reaches the response -----------------------


def test_rejected_key_response_never_includes_the_key_value_itself(client) -> None:
    # The message handed to the error (constructed the same way the real
    # call sites build it -- naming the status, never the key) is all the
    # handler has to work with; this proves it is passed through verbatim
    # and nothing in the handler itself reintroduces the key value.
    app.dependency_overrides[get_db] = _raising_dependency(
        embeddings.GeminiKeyRejectedError(
            "GEMINI_API_KEY was rejected by Gemini (status 401)", status_code=401
        )
    )

    response = client.get("/threads")

    assert "super-secret-value" not in response.text
    assert response.json()["detail"]["message"] == (
        "GEMINI_API_KEY was rejected by Gemini (status 401)"
    )
