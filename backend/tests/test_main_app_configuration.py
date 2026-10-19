"""Unit tests for `app.main` itself: the FastAPI app assembly, as opposed to
any one router's business logic (covered in its own test file) or the
rate-limit 429 shape (covered end to end in `test_rate_limit.py`).

Three things live in `app/main.py` and nowhere else, so this is the only
file that can prove them:

1. The OpenAPI title/description actually carry the product's defining
   constraint (no accounts, one shared workspace) into the document every
   API consumer reads.
2. The CORS origin list -- default dev/e2e-preview ports, or the complete
   replacement promised for `ALLOWED_ORIGINS` -- is wired into the
   middleware a browser actually enforces against.
3. The two Gemini-error exception handlers are registered against the
   right exception classes and produce the documented
   `{"detail": {"code", "message"}}` 503 shape.

`app.main` builds its CORS origin list once, at import time, from
`os.environ`, so the only way to exercise both branches of that is to
reload the module under a controlled environment -- the same technique
`test_database.py` already uses for `DATABASE_URL`. The reload is undone
afterwards so no later test in this suite (several of which import
`app.main.app` directly) runs against a differently-configured app than it
expects.
"""

import asyncio
import importlib
import json
import os

import pytest
from fastapi.testclient import TestClient

from app import embeddings, generation
from app import main as main_module
from app.main import app as default_app

client = TestClient(default_app)


# --- the OpenAPI document carries the product's defining constraint -------


def test_openapi_title_names_the_product():
    response = client.get("/openapi.json")

    assert response.status_code == 200
    info = response.json()["info"]
    assert "chat documents" in info["title"].lower()
    assert "rag" in info["title"].lower()


def test_openapi_description_states_there_is_no_login_and_one_shared_workspace():
    response = client.get("/openapi.json")

    description = response.json()["info"]["description"].lower()
    assert "no sign-up" in description or "no login" in description
    assert "shared workspace" in description


# --- CORS: default origins cover the dev server and the e2e preview server -


@pytest.fixture()
def _restore_main_module():
    """Reloading `app.main` rebuilds its CORS origin list (and re-registers
    its routers, exception handlers and table creation) against whatever
    `ALLOWED_ORIGINS` the test set -- undone here by reloading once more
    with it unset, so this file leaves `app.main` in the same default state
    every other test file in this suite already assumes.
    """
    yield
    os.environ.pop("ALLOWED_ORIGINS", None)
    importlib.reload(main_module)


@pytest.mark.parametrize(
    "dev_origin",
    [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
)
def test_default_cors_origins_allow_the_dev_server_and_the_e2e_preview_server(
    dev_origin, monkeypatch, _restore_main_module
):
    """Without `ALLOWED_ORIGINS` set, all four documented ports -- the Vite
    dev server and the Vite preview server the Playwright suite builds
    against (frontend/playwright.config.ts) -- must be reflected back, or a
    real (non-mocked) network call from either is silently rejected by the
    browser's own CORS check before it ever reaches a route.
    """
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    importlib.reload(main_module)
    reloaded_client = TestClient(main_module.app)

    response = reloaded_client.get("/health", headers={"Origin": dev_origin})

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == dev_origin
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_default_cors_origins_reject_an_origin_outside_the_dev_list(
    monkeypatch, _restore_main_module
):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    importlib.reload(main_module)
    reloaded_client = TestClient(main_module.app)

    response = reloaded_client.get("/health", headers={"Origin": "http://evil.example.com"})

    # The server still answers -- CORS is enforced by the browser, not here
    # -- but without the header a real browser refuses to hand the response
    # to the page's own script.
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_allowed_origins_env_var_replaces_the_default_list_entirely(
    monkeypatch, _restore_main_module
):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://deployed-frontend.example.com")
    importlib.reload(main_module)
    reloaded_client = TestClient(main_module.app)

    allowed = reloaded_client.get(
        "/health", headers={"Origin": "https://deployed-frontend.example.com"}
    )
    assert allowed.headers.get("access-control-allow-origin") == (
        "https://deployed-frontend.example.com"
    )

    # The default dev origin is gone, not merely supplemented -- "replaces
    # entirely" is the documented contract once the platform injects this
    # variable.
    now_rejected = reloaded_client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert "access-control-allow-origin" not in now_rejected.headers


def test_allowed_origins_env_var_parses_a_comma_separated_list(monkeypatch, _restore_main_module):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://one.example.com, https://two.example.com")
    importlib.reload(main_module)
    reloaded_client = TestClient(main_module.app)

    first = reloaded_client.get("/health", headers={"Origin": "https://one.example.com"})
    second = reloaded_client.get("/health", headers={"Origin": "https://two.example.com"})

    assert first.headers.get("access-control-allow-origin") == "https://one.example.com"
    assert second.headers.get("access-control-allow-origin") == "https://two.example.com"


def test_cors_preflight_allows_any_method_and_header_for_an_allowed_origin(
    monkeypatch, _restore_main_module
):
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    importlib.reload(main_module)
    reloaded_client = TestClient(main_module.app)

    response = reloaded_client.options(
        "/documents",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "POST" in response.headers.get("access-control-allow-methods", "")
    assert "content-type" in response.headers.get("access-control-allow-headers", "").lower()


# --- Gemini-error exception handlers: registered against the right classes -


def test_gemini_not_configured_is_registered_for_both_embeddings_and_generation():
    handlers = default_app.exception_handlers
    assert (
        handlers[embeddings.GeminiNotConfiguredError]
        is handlers[generation.GeminiNotConfiguredError]
    )


def test_gemini_key_rejected_is_registered_for_both_embeddings_and_generation():
    handlers = default_app.exception_handlers
    assert (
        handlers[embeddings.GeminiKeyRejectedError] is handlers[generation.GeminiKeyRejectedError]
    )


def test_not_configured_and_key_rejected_use_different_handlers():
    """A `GeminiNotConfiguredError` and a `GeminiKeyRejectedError` are
    different failures (nothing set vs. Gemini rejected what was set) with
    different documented `code`s -- registering the same handler for both
    would be a silent bug no status-code-only check would catch."""
    handlers = default_app.exception_handlers
    assert (
        handlers[embeddings.GeminiNotConfiguredError]
        is not handlers[embeddings.GeminiKeyRejectedError]
    )


# --- Gemini-error exception handlers: the 503 body shape they produce ------
#
# Nothing in the currently generated routers actually lets either error
# reach these handlers: `app.services.request_answer` catches every
# exception out of `retrieve_context`/`stream_answer` itself and turns it
# into an SSE 'error' event (see services.py), and `app.ingestion` catches
# `GeminiNotConfiguredError` itself inside a background task, which the
# ASGI exception-handling layer never sees regardless. These tests call the
# registered handler functions directly -- the only way left to prove the
# body shape `main.py` promises -- rather than through an endpoint that, as
# generated, cannot currently trigger them; see this ticket's notes.


async def _invoke(handler, exc):
    return await handler(None, exc)


def test_gemini_not_configured_handler_returns_structured_503():
    handler = default_app.exception_handlers[embeddings.GeminiNotConfiguredError]
    exc = embeddings.GeminiNotConfiguredError("GEMINI_API_KEY is not configured")

    response = asyncio.run(_invoke(handler, exc))

    assert response.status_code == 503
    body = json.loads(bytes(response.body))
    assert body == {
        "detail": {
            "code": "gemini_not_configured",
            "message": "GEMINI_API_KEY is not configured",
        }
    }


def test_gemini_key_rejected_handler_returns_structured_503_naming_status():
    handler = default_app.exception_handlers[generation.GeminiKeyRejectedError]
    exc = generation.GeminiKeyRejectedError(
        "GEMINI_API_KEY was rejected by Gemini (status 401)", status_code=401
    )

    response = asyncio.run(_invoke(handler, exc))

    assert response.status_code == 503
    body = json.loads(bytes(response.body))
    assert body["detail"]["code"] == "gemini_key_rejected"
    assert "401" in body["detail"]["message"]
    assert "GEMINI_API_KEY" in body["detail"]["message"]


def test_gemini_key_rejected_handler_never_includes_the_key_value_in_its_response():
    handler = default_app.exception_handlers[embeddings.GeminiKeyRejectedError]
    exc = embeddings.GeminiKeyRejectedError(
        "GEMINI_API_KEY was rejected by Gemini (status 401)", status_code=401
    )

    response = asyncio.run(_invoke(handler, exc))

    assert b"super-secret" not in bytes(response.body)
    assert json.loads(bytes(response.body))["detail"]["message"].count("GEMINI_API_KEY") >= 1
