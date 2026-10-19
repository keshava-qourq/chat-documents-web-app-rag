"""Unit tests for `app.config`.

Other suites (`test_document_cap.py`, `test_rate_limit.py`) already exercise
`document_cap`, `rate_limit_chat_per_minute` and `rate_limit_uploads_per_hour`
end to end through the API they gate, so this file does not repeat that --
it tests each reader in `app.config` directly and in isolation, including
the ones (`chunk_size`, `chunk_overlap`, `embedding_max_retries`,
`embedding_batch_size`, `gemini_api_key`) that no other suite reaches
directly. Every reader is a thin `os.getenv(...)` wrapper, so the contract
worth pinning down is: unset falls back to the documented default, and a set
value is parsed and returned, for every one of them -- plus `gemini_api_key`'s
own documented quirk that an empty string counts as unset.
"""

from app import config


# --- gemini_api_key: None when unset, empty-string also counts as unset ----


def test_gemini_api_key_is_none_when_env_var_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    assert config.gemini_api_key() is None


def test_gemini_api_key_is_none_when_env_var_is_empty_string(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "")

    assert config.gemini_api_key() is None


def test_gemini_api_key_returns_the_configured_value(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "a-real-key")

    assert config.gemini_api_key() == "a-real-key"


# --- document_cap -------------------------------------------------------


def test_document_cap_falls_back_to_default_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("DOCUMENT_CAP", raising=False)

    assert config.document_cap() == config.DOCUMENT_CAP_DEFAULT


def test_document_cap_reads_overridden_value(monkeypatch) -> None:
    monkeypatch.setenv("DOCUMENT_CAP", "42")

    assert config.document_cap() == 42


# --- rate_limit_chat_per_minute ------------------------------------------


def test_rate_limit_chat_per_minute_falls_back_to_default_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("RATE_LIMIT_CHAT_PER_MIN", raising=False)

    assert config.rate_limit_chat_per_minute() == config.RATE_LIMIT_CHAT_PER_MIN_DEFAULT


def test_rate_limit_chat_per_minute_reads_overridden_value(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_CHAT_PER_MIN", "5")

    assert config.rate_limit_chat_per_minute() == 5


# --- rate_limit_uploads_per_hour -----------------------------------------


def test_rate_limit_uploads_per_hour_falls_back_to_default_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("RATE_LIMIT_UPLOADS_PER_HOUR", raising=False)

    assert config.rate_limit_uploads_per_hour() == config.RATE_LIMIT_UPLOADS_PER_HOUR_DEFAULT


def test_rate_limit_uploads_per_hour_reads_overridden_value(monkeypatch) -> None:
    monkeypatch.setenv("RATE_LIMIT_UPLOADS_PER_HOUR", "3")

    assert config.rate_limit_uploads_per_hour() == 3


# --- chunk_size -----------------------------------------------------------


def test_chunk_size_falls_back_to_default_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("CHUNK_SIZE", raising=False)

    assert config.chunk_size() == config.CHUNK_SIZE_DEFAULT


def test_chunk_size_reads_overridden_value(monkeypatch) -> None:
    monkeypatch.setenv("CHUNK_SIZE", "500")

    assert config.chunk_size() == 500


# --- chunk_overlap ----------------------------------------------------------


def test_chunk_overlap_falls_back_to_default_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("CHUNK_OVERLAP", raising=False)

    assert config.chunk_overlap() == config.CHUNK_OVERLAP_DEFAULT


def test_chunk_overlap_reads_overridden_value(monkeypatch) -> None:
    monkeypatch.setenv("CHUNK_OVERLAP", "50")

    assert config.chunk_overlap() == 50


# --- embedding_max_retries --------------------------------------------------


def test_embedding_max_retries_falls_back_to_default_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_MAX_RETRIES", raising=False)

    assert config.embedding_max_retries() == config.EMBEDDING_MAX_RETRIES_DEFAULT


def test_embedding_max_retries_reads_overridden_value(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_MAX_RETRIES", "7")

    assert config.embedding_max_retries() == 7


# --- embedding_batch_size ----------------------------------------------------


def test_embedding_batch_size_falls_back_to_default_when_unset(monkeypatch) -> None:
    monkeypatch.delenv("EMBEDDING_BATCH_SIZE", raising=False)

    assert config.embedding_batch_size() == config.EMBEDDING_BATCH_SIZE_DEFAULT


def test_embedding_batch_size_reads_overridden_value(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_BATCH_SIZE", "32")

    assert config.embedding_batch_size() == 32


# --- MAX_UPLOAD_FILE_BYTES: fixed constant, not environment-configurable ----


def test_max_upload_file_bytes_is_twenty_five_megabytes() -> None:
    assert config.MAX_UPLOAD_FILE_BYTES == 25 * 1024 * 1024
