"""Unit tests for `app/config.py` itself.

This ticket carries no acceptance criteria of its own -- `config.py` is a
pure set of environment reads with no endpoint attached. These tests follow
the contract documented in the module's own docstrings instead: every
setting function reads its own named env var, falls back to its documented
default when that var is unset, and `gemini_api_key()` additionally treats
an empty string the same as unset.

Other suites (`test_document_cap.py`, `test_rate_limit.py`,
`test_ingestion.py`, `test_gemini_config_error.py`) already exercise several
of these settings indirectly through the endpoints and pipelines that
consume them; this file instead calls the functions in `app.config`
directly, so a regression in the reader itself fails here even if every
consumer happens to pass its own default through untouched.
"""

import pytest

from app import config


# --- gemini_api_key ---------------------------------------------------------


def test_gemini_api_key_is_none_when_env_var_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert config.gemini_api_key() is None


def test_gemini_api_key_is_none_when_env_var_is_set_to_empty_string(monkeypatch) -> None:
    """An empty string must disable the feature exactly as a missing
    variable would, not be handed to the SDK as a key."""
    monkeypatch.setenv("GEMINI_API_KEY", "")
    assert config.gemini_api_key() is None


def test_gemini_api_key_returns_the_configured_value(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "a-real-key")
    assert config.gemini_api_key() == "a-real-key"


# --- document_cap ------------------------------------------------------------


def test_document_cap_defaults_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("DOCUMENT_CAP", raising=False)
    assert config.document_cap() == config.DOCUMENT_CAP_DEFAULT


def test_document_cap_reads_env_override(monkeypatch) -> None:
    monkeypatch.setenv("DOCUMENT_CAP", "42")
    assert config.document_cap() == 42


# --- rate_limit_chat_per_minute ----------------------------------------------


def test_rate_limit_chat_per_minute_defaults_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("RATE_LIMIT_CHAT_PER_MIN", raising=False)
    assert config.rate_limit_chat_per_minute() == config.RATE_LIMIT_CHAT_PER_MIN_DEFAULT


def test_rate_limit_chat_per_minute_reads_env_override(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_CHAT_PER_MIN", "99")
    assert config.rate_limit_chat_per_minute() == 99


# --- rate_limit_uploads_per_hour ----------------------------------------------


def test_rate_limit_uploads_per_hour_defaults_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("RATE_LIMIT_UPLOADS_PER_HOUR", raising=False)
    assert config.rate_limit_uploads_per_hour() == config.RATE_LIMIT_UPLOADS_PER_HOUR_DEFAULT


def test_rate_limit_uploads_per_hour_reads_env_override(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_HOUR", "17")
    assert config.rate_limit_uploads_per_hour() == 17


# --- chunk_size / chunk_overlap ----------------------------------------------


def test_chunk_size_defaults_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("CHUNK_SIZE", raising=False)
    assert config.chunk_size() == config.CHUNK_SIZE_DEFAULT


def test_chunk_size_reads_env_override(monkeypatch) -> None:
    monkeypatch.setenv("CHUNK_SIZE", "500")
    assert config.chunk_size() == 500


def test_chunk_overlap_defaults_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("CHUNK_OVERLAP", raising=False)
    assert config.chunk_overlap() == config.CHUNK_OVERLAP_DEFAULT


def test_chunk_overlap_reads_env_override(monkeypatch) -> None:
    monkeypatch.setenv("CHUNK_OVERLAP", "50")
    assert config.chunk_overlap() == 50


# --- embedding_max_retries / embedding_batch_size ----------------------------


def test_embedding_max_retries_defaults_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_MAX_RETRIES", raising=False)
    assert config.embedding_max_retries() == config.EMBEDDING_MAX_RETRIES_DEFAULT


def test_embedding_max_retries_reads_env_override(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "7")
    assert config.embedding_max_retries() == 7


def test_embedding_batch_size_defaults_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_BATCH_SIZE", raising=False)
    assert config.embedding_batch_size() == config.EMBEDDING_BATCH_SIZE_DEFAULT


def test_embedding_batch_size_reads_env_override(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "4")
    assert config.embedding_batch_size() == 4


# --- malformed values surface a clear error rather than a silent fallback ---


@pytest.mark.parametrize(
    "env_var, reader",
    [
        ("DOCUMENT_CAP", config.document_cap),
        ("RATE_LIMIT_CHAT_PER_MIN", config.rate_limit_chat_per_minute),
        ("RATE_LIMIT_UPLOADS_PER_HOUR", config.rate_limit_uploads_per_hour),
        ("CHUNK_SIZE", config.chunk_size),
        ("CHUNK_OVERLAP", config.chunk_overlap),
        ("EMBEDDING_MAX_RETRIES", config.embedding_max_retries),
        ("EMBEDDING_BATCH_SIZE", config.embedding_batch_size),
    ],
)
def test_non_integer_env_value_raises_rather_than_falling_back_to_the_default(
    monkeypatch, env_var, reader
) -> None:
    """These readers call `int()` directly with no `try/except`, so a
    misconfigured deployment (e.g. `DOCUMENT_CAP=abc`) must fail loudly at
    the point of use instead of silently reverting to the hard-coded
    default and hiding the misconfiguration."""
    monkeypatch.setenv(env_var, "not-an-integer")
    with pytest.raises(ValueError):
        reader()
