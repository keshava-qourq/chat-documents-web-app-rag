"""Unit tests for `app.main`'s CORS configuration.

The SPA runs on a different origin than the API, so the browser enforces
whatever `CORSMiddleware` in `main.py` allows -- the dev-server defaults, and
the `ALLOWED_ORIGINS` env var that is meant to replace them in a real
deployment. Nothing in the rest of the suite ever sends an `Origin` header or
inspects `Access-Control-Allow-Origin`, so this behaviour -- entirely
`main.py`'s own -- has no coverage anywhere else in this repo.

`ALLOWED_ORIGINS` is read once, at import time, into a module-level list, so
exercising both branches (unset -> dev defaults; set -> parsed from the env
var) requires reimporting `app.main` with the env var changed first. Every
test here reloads the module and restores it to its unset state again
afterwards, so no other test in the suite -- which imports the same `app.main`
module once at collection time, before any test body runs -- is affected by
the reload.
"""

import importlib

from fastapi.testclient import TestClient

import app.main as main_module


def _reload_with_env_restored_after():
    importlib.reload(main_module)
    return main_module.app


def test_dev_default_origin_is_allowed_when_allowed_origins_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    app = _reload_with_env_restored_after()
    try:
        client = TestClient(app)
        response = client.get("/health", headers={"Origin": "http://localhost:5173"})

        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    finally:
        importlib.reload(main_module)


def test_an_unlisted_origin_gets_no_cors_header_by_default(monkeypatch) -> None:
    monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
    app = _reload_with_env_restored_after()
    try:
        client = TestClient(app)
        response = client.get("/health", headers={"Origin": "https://not-allowed.example"})

        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers
    finally:
        importlib.reload(main_module)


def test_allowed_origins_env_var_is_parsed_as_a_trimmed_comma_separated_list(monkeypatch) -> None:
    monkeypatch.setenv("ALLOWED_ORIGINS", " https://example.com , https://two.example.com  ")
    app = _reload_with_env_restored_after()
    try:
        client = TestClient(app)

        first = client.get("/health", headers={"Origin": "https://example.com"})
        assert first.headers["access-control-allow-origin"] == "https://example.com"

        second = client.get("/health", headers={"Origin": "https://two.example.com"})
        assert second.headers["access-control-allow-origin"] == "https://two.example.com"

        # Setting ALLOWED_ORIGINS replaces the dev defaults; it does not
        # merely extend them.
        dev_default = client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert "access-control-allow-origin" not in dev_default.headers
    finally:
        monkeypatch.delenv("ALLOWED_ORIGINS", raising=False)
        importlib.reload(main_module)
