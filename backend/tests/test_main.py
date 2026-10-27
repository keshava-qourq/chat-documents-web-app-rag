"""Unit tests for `app/main.py` itself: the application entrypoint.

This ticket carries no acceptance criteria of its own. `main.py` wires
together pieces other suites already exercise through the endpoints they
belong to (`/health` in `test_health.py`, the chat endpoint's own pre-flight
503 in `test_gemini_config_error.py`, 429s in `test_rate_limit.py`) -- this
file instead targets the two things `main.py` does that nothing else in the
suite drives: the CORS origin list built from `ALLOWED_ORIGINS`, and the
four `add_exception_handler` registrations that turn a `GeminiNotConfiguredError`
/ `GeminiKeyRejectedError` raised from *any* route (not just the one
hand-written pre-flight check in `routers/threads.py`) into the documented
`{"detail": {"code": ..., "message": ...}}` 503 shape.

`ALLOWED_ORIGINS` is read once, at import time, into a module-level list
(`main.py`'s own comment: "that replaces this default list entirely") --
so, mirroring the reload pattern `test_database.py` and `test_config.py`
already use for other import-time env reads, these tests reload `app.main`
under a monkeypatched environment rather than trying to observe the
already-built `CORSMiddleware` from outside. The `_restore_main_module`
fixture always reloads the module back to its ambient-environment state
afterwards, so no other test in the suite (several of which import
`app.main.app` directly) is left pointed at a stale, test-configured app.
"""

import importlib
import os

import pytest
from fastapi.testclient import TestClient

from app import embeddings, generation
from app import main as main_module


@pytest.fixture()
def _restore_main_module():
    original_allowed_origins = os.environ.get("ALLOWED_ORIGINS")
    try:
        yield
    finally:
        if original_allowed_origins is None:
            os.environ.pop("ALLOWED_ORIGINS", None)
        else:
            os.environ["ALLOWED_ORIGINS"] = original_allowed_origins
        importlib.reload(main_module)


# --- CORS: default (dev) origins when ALLOWED_ORIGINS is unset --------------


def test_cors_allows_the_vite_dev_origin_when_allowed_origins_is_unset(
    monkeypatch, _restore_main_module
) -> None:
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    reloaded = importlib.reload(main_module)
    client = TestClient(reloaded.app)

    response = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_allows_the_vite_preview_origin_the_e2e_suite_uses_when_unset(
    monkeypatch, _restore_main_module
) -> None:
    """The e2e suite builds the SPA and serves it from Vite's preview server
    (port 4173), per `playwright.config.ts` -- a regression that drops that
    origin from the default list would silently fail every real (non-mocked)
    network call the e2e suite makes, without a single unit test noticing."""
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    reloaded = importlib.reload(main_module)
    client = TestClient(reloaded.app)

    response = client.get("/health", headers={"Origin": "http://localhost:4173"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:4173"


def test_cors_does_not_allow_an_origin_outside_the_default_list(
    monkeypatch, _restore_main_module
) -> None:
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    reloaded = importlib.reload(main_module)
    client = TestClient(reloaded.app)

    response = client.get("/health", headers={"Origin": "http://evil.example"})

    # CORS is enforced by the browser, not the server: the request itself
    # still succeeds, it just carries no header telling a browser it may
    # read the response from that origin.
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


# --- CORS: ALLOWED_ORIGINS replaces the default list entirely ---------------


def test_cors_uses_allowed_origins_env_var_once_it_is_set(monkeypatch, _restore_main_module) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    reloaded = importlib.reload(main_module)
    client = TestClient(reloaded.app)

    response = client.get("/health", headers={"Origin": "https://app.example.com"})

    assert response.headers["access-control-allow-origin"] == "https://app.example.com"


def test_cors_allowed_origins_env_var_replaces_rather_than_extends_the_dev_defaults(
    monkeypatch, _restore_main_module
) -> None:
    """Per `main.py`'s own comment, the platform-injected `ALLOWED_ORIGINS`
    "replaces this default list entirely" -- a deployed app must not keep
    trusting the local dev server's origin once a real frontend origin is
    configured."""
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    reloaded = importlib.reload(main_module)
    client = TestClient(reloaded.app)

    response = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert "access-control-allow-origin" not in response.headers


def test_cors_allowed_origins_env_var_is_comma_separated_and_trims_whitespace(
    monkeypatch, _restore_main_module
) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", " https://a.example.com , https://b.example.com ")
    reloaded = importlib.reload(main_module)
    client = TestClient(reloaded.app)

    first = client.get("/health", headers={"Origin": "https://a.example.com"})
    second = client.get("/health", headers={"Origin": "https://b.example.com"})

    assert first.headers["access-control-allow-origin"] == "https://a.example.com"
    assert second.headers["access-control-allow-origin"] == "https://b.example.com"


def test_cors_allowed_origins_set_to_only_blank_entries_falls_back_to_dev_defaults(
    monkeypatch, _restore_main_module
) -> None:
    """`main.py` builds its list with `if o.strip()`, dropping blank
    entries -- a value like `","` (e.g. a misconfigured platform variable)
    must fall back to the dev defaults (`_allowed_origins or _dev_origins`),
    not silently become an empty, allow-nothing list."""
    monkeypatch.setenv("ALLOWED_ORIGINS", " , ")
    reloaded = importlib.reload(main_module)
    client = TestClient(reloaded.app)

    response = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


# --- registered exception handlers: Gemini config errors from any route ----

_GEMINI_HANDLER_CASES = [
    pytest.param(
        embeddings.GeminiNotConfiguredError,
        lambda cls: cls("GEMINI_API_KEY is not configured"),
        "gemini_not_configured",
        id="embeddings-not-configured",
    ),
    pytest.param(
        generation.GeminiNotConfiguredError,
        lambda cls: cls("GEMINI_API_KEY is not configured"),
        "gemini_not_configured",
        id="generation-not-configured",
    ),
    pytest.param(
        embeddings.GeminiKeyRejectedError,
        lambda cls: cls("GEMINI_API_KEY was rejected by Gemini (status 401)", status_code=401),
        "gemini_key_rejected",
        id="embeddings-key-rejected",
    ),
    pytest.param(
        generation.GeminiKeyRejectedError,
        lambda cls: cls("GEMINI_API_KEY was rejected by Gemini (status 403)", status_code=403),
        "gemini_key_rejected",
        id="generation-key-rejected",
    ),
]


@pytest.mark.parametrize("exc_class, build, expected_code", _GEMINI_HANDLER_CASES)
def test_each_registered_gemini_error_class_becomes_the_documented_503_shape(
    exc_class, build, expected_code
) -> None:
    """`main.py` registers its 503 handlers against four distinct exception
    classes (one `GeminiNotConfiguredError` and one `GeminiKeyRejectedError`
    per module) rather than a shared base type. Nothing in the rest of the
    suite ever lets one of these escape a route handler -- `routers/threads.py`
    checks `gemini_api_key()` itself and raises its own `HTTPException` with a
    matching body instead, and `app.services.request_answer` catches
    `generation`'s versions internally and emits an SSE error event, never
    re-raising them. So this registration is only ever exercised here: a
    throwaway probe route is attached to the real, already-configured `app`
    for the duration of one test, to raise each class in turn and confirm the
    *registered handler* -- not a coincidentally identical hand-written one --
    is what produces the response.
    """
    app_under_test = main_module.app
    path = f"/_test_probe_{exc_class.__module__.replace('.', '_')}_{exc_class.__name__}"

    async def _raise_it():
        raise build(exc_class)

    app_under_test.add_api_route(path, _raise_it, methods=["GET"])
    try:
        client = TestClient(app_under_test)
        response = client.get(path)
    finally:
        app_under_test.router.routes = [
            route for route in app_under_test.router.routes if getattr(route, "path", None) != path
        ]

    assert response.status_code == 503
    body = response.json()
    assert body["detail"]["code"] == expected_code
    assert "GEMINI_API_KEY" in body["detail"]["message"]


def test_key_rejected_handler_never_echoes_the_actual_key_value() -> None:
    """The handler only ever serialises `str(exc)` -- it must not, say, also
    include request state or anything else that could carry the real key."""
    app_under_test = main_module.app
    path = "/_test_probe_key_value_leak"

    async def _raise_it():
        raise embeddings.GeminiKeyRejectedError(
            "GEMINI_API_KEY was rejected by Gemini (status 401)", status_code=401
        )

    app_under_test.add_api_route(path, _raise_it, methods=["GET"])
    try:
        client = TestClient(app_under_test)
        response = client.get(path, headers={"Authorization": "Bearer super-secret-value"})
    finally:
        app_under_test.router.routes = [
            route for route in app_under_test.router.routes if getattr(route, "path", None) != path
        ]

    assert "super-secret-value" not in response.text
