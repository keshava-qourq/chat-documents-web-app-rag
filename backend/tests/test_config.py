"""Unit tests for `app.config`.

Every reader in `app.config` is exercised directly here -- its documented
default when the env var is unset, the env var overriding it, and (for
`gemini_api_key`) the "empty string counts as unset" rule the module's own
docstring calls out by name. Other suites already prove these readers work
*through* the endpoints that consume them (`test_document_cap.py`,
`test_rate_limit.py`, `app/tests/test_gemini_config_error.py` for
`gemini_api_key`'s missing/rejected-key branches) -- this file is the one
place every function in the module is called directly, so a reader that
silently stops reading its env var, or stops falling back to its default,
fails here even if every caller happens to pass its own value and never
notices.

Uses `monkeypatch.setenv`/`monkeypatch.delenv` exactly as the rest of the
suite does, so no fixture from `conftest.py` is needed: these functions
read `os.environ` directly and touch no database, storage or network.
"""

import pytest

from app import config


# --- gemini_api_key: unset, empty, set, and read-at-call-time -------------


def test_gemini_api_key_is_none_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert config.gemini_api_key() is None


def test_gemini_api_key_is_none_when_set_to_empty_string(monkeypatch) -> None:
    # Documented explicitly in the module: an empty string must disable the
    # feature exactly like a missing variable, not be passed to the SDK.
    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert config.gemini_api_key() is None


def test_gemini_api_key_returns_the_configured_value(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "a-real-looking-key")
    assert config.gemini_api_key() == "a-real-looking-key"


def test_gemini_api_key_is_read_fresh_on_every_call_not_cached_from_import(monkeypatch) -> None:
    # The module's own contract: every value is read through a function, not
    # a module-level constant, precisely so a later change to the
    # environment is visible without reimporting anything.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert config.gemini_api_key() is None

    monkeypatch.setenv("GEMINI_API_KEY", "set-after-the-first-call")
    assert config.gemini_api_key() == "set-after-the-first-call"

    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert config.gemini_api_key() is None


# --- document_cap -----------------------------------------------------------


def test_document_cap_falls_back_to_the_documented_default(monkeypatch) -> None:
    monkeypatch.delenv("DOCUMENT_CAP", raising=False)
    assert config.document_cap() == config.DOCUMENT_CAP_DEFAULT


def test_document_cap_is_read_from_its_env_var(monkeypatch) -> None:
    monkeypatch.setenv("DOCUMENT_CAP", "42")
    assert config.document_cap() == 42


# --- rate_limit_chat_per_minute ---------------------------------------------


def test_rate_limit_chat_per_minute_falls_back_to_the_documented_default(monkeypatch) -> None:
    monkeypatch.delenv("RATE_LIMIT_CHAT_PER_MIN", raising=False)
    assert config.rate_limit_chat_per_minute() == config.RATE_LIMIT_CHAT_PER_MIN_DEFAULT


def test_rate_limit_chat_per_minute_is_read_from_its_env_var(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_CHAT_PER_MIN", "7")
    assert config.rate_limit_chat_per_minute() == 7


# --- rate_limit_uploads_per_hour --------------------------------------------


def test_rate_limit_uploads_per_hour_falls_back_to_the_documented_default(monkeypatch) -> None:
    monkeypatch.delenv("RATE_LIMIT_UPLOADS_PER_HOUR", raising=False)
    assert config.rate_limit_uploads_per_hour() == config.RATE_LIMIT_UPLOADS_PER_HOUR_DEFAULT


def test_rate_limit_uploads_per_hour_is_read_from_its_env_var(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_HOUR", "3")
    assert config.rate_limit_uploads_per_hour() == 3


# --- chunk_size --------------------------------------------------------------


def test_chunk_size_falls_back_to_the_documented_default(monkeypatch) -> None:
    monkeypatch.delenv("CHUNK_SIZE", raising=False)
    assert config.chunk_size() == config.CHUNK_SIZE_DEFAULT


def test_chunk_size_is_read_from_its_env_var(monkeypatch) -> None:
    monkeypatch.setenv("CHUNK_SIZE", "500")
    assert config.chunk_size() == 500


# --- chunk_overlap -----------------------------------------------------------


def test_chunk_overlap_falls_back_to_the_documented_default(monkeypatch) -> None:
    monkeypatch.delenv("CHUNK_OVERLAP", raising=False)
    assert config.chunk_overlap() == config.CHUNK_OVERLAP_DEFAULT


def test_chunk_overlap_is_read_from_its_env_var(monkeypatch) -> None:
    monkeypatch.setenv("CHUNK_OVERLAP", "50")
    assert config.chunk_overlap() == 50


# --- embedding_max_retries ----------------------------------------------------


def test_embedding_max_retries_falls_back_to_the_documented_default(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_MAX_RETRIES", raising=False)
    assert config.embedding_max_retries() == config.EMBEDDING_MAX_RETRIES_DEFAULT


def test_embedding_max_retries_is_read_from_its_env_var(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "9")
    assert config.embedding_max_retries() == 9


# --- embedding_batch_size ------------------------------------------------------


def test_embedding_batch_size_falls_back_to_the_documented_default(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_BATCH_SIZE", raising=False)
    assert config.embedding_batch_size() == config.EMBEDDING_BATCH_SIZE_DEFAULT


def test_embedding_batch_size_is_read_from_its_env_var(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "32")
    assert config.embedding_batch_size() == 32


# --- invalid values are surfaced, not silently swallowed --------------------


@pytest.mark.parametrize(
    "reader, env_var",
    [
        (config.document_cap, "DOCUMENT_CAP"),
        (config.rate_limit_chat_per_minute, "RATE_LIMIT_CHAT_PER_MIN"),
        (config.rate_limit_uploads_per_hour, "RATE_LIMIT_UPLOADS_PER_HOUR"),
        (config.chunk_size, "CHUNK_SIZE"),
        (config.chunk_overlap, "CHUNK_OVERLAP"),
        (config.embedding_max_retries, "EMBEDDING_MAX_RETRIES"),
        (config.embedding_batch_size, "EMBEDDING_BATCH_SIZE"),
    ],
)
def test_non_integer_env_value_raises_rather_than_being_silently_ignored(
    monkeypatch, reader, env_var
) -> None:
    # Every one of these readers does a bare `int(...)` conversion with no
    # try/except: a misconfigured, non-numeric value must fail loudly at the
    # point it is read, not be swallowed into the default as if it were
    # never set.
    monkeypatch.setenv(env_var, "not-a-number")
    with pytest.raises(ValueError):
        reader()


# --- MAX_UPLOAD_FILE_BYTES: a plain constant, not an env-backed reader -----


def test_max_upload_file_bytes_is_twenty_five_megabytes() -> None:
    assert config.MAX_UPLOAD_FILE_BYTES == 25 * 1024 * 1024
