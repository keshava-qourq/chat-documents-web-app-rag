"""Unit tests for `backend/app/storage.py`: the boto3 wrapper around the
MinIO bucket that holds original uploads.

Exercises the module's own functions directly rather than through the
documents API -- other suites (`test_documents.py`,
`test_document_delete.py`) already cover storage through the HTTP surface
with a fake object store standing in for this module entirely. This file is
the one place that actually calls into `storage.py`'s logic: endpoint URL
normalisation, the client's configured credentials, bucket auto-creation,
and the "failures here must not block the row delete" contract on
`delete_object`. boto3's `S3` client is monkeypatched throughout -- no live
MinIO connection is ever attempted.
"""

import importlib
from unittest.mock import MagicMock

from app import storage


# --- _endpoint_url ------------------------------------------------------------


def test_endpoint_url_is_empty_when_minio_endpoint_is_unset(monkeypatch):
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)

    assert storage._endpoint_url() == ""


def test_endpoint_url_prepends_http_when_scheme_is_missing(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")

    assert storage._endpoint_url() == "http://minio:9000"


def test_endpoint_url_leaves_an_explicit_http_scheme_untouched(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")

    assert storage._endpoint_url() == "http://minio:9000"


def test_endpoint_url_leaves_an_explicit_https_scheme_untouched(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "https://minio.example.com")

    assert storage._endpoint_url() == "https://minio.example.com"


# --- BUCKET_NAME ----------------------------------------------------------------
# `BUCKET_NAME` is read from the environment once, at import time, so proving
# the env var actually drives it requires reloading the module; each test
# restores the module to its original (unset) state afterwards so it cannot
# leak into any other test in the suite.


def test_bucket_name_defaults_to_documents_when_minio_bucket_is_unset(monkeypatch):
    monkeypatch.delenv("MINIO_BUCKET", raising=False)

    reloaded = importlib.reload(storage)
    try:
        assert reloaded.BUCKET_NAME == "documents"
    finally:
        monkeypatch.delenv("MINIO_BUCKET", raising=False)
        importlib.reload(storage)


def test_bucket_name_honours_minio_bucket_env_var(monkeypatch):
    monkeypatch.setenv("MINIO_BUCKET", "custom-bucket")

    reloaded = importlib.reload(storage)
    try:
        assert reloaded.BUCKET_NAME == "custom-bucket"
    finally:
        monkeypatch.delenv("MINIO_BUCKET", raising=False)
        importlib.reload(storage)


# --- get_client -----------------------------------------------------------------


def test_get_client_passes_configured_endpoint_and_credentials_to_boto3(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "the-access-key")
    monkeypatch.setenv("MINIO_SECRET_KEY", "the-secret-key")
    captured = {}

    def fake_boto3_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(storage.boto3, "client", fake_boto3_client)

    storage.get_client()

    assert captured["service_name"] == "s3"
    assert captured["endpoint_url"] == "http://minio:9000"
    assert captured["aws_access_key_id"] == "the-access-key"
    assert captured["aws_secret_access_key"] == "the-secret-key"


def test_get_client_returns_a_new_client_on_every_call(monkeypatch):
    created = []

    def fake_boto3_client(service_name, **kwargs):
        client = MagicMock()
        created.append(client)
        return client

    monkeypatch.setattr(storage.boto3, "client", fake_boto3_client)

    first = storage.get_client()
    second = storage.get_client()

    assert first is created[0]
    assert second is created[1]
    assert first is not second


# --- ensure_bucket --------------------------------------------------------------


def test_ensure_bucket_is_a_no_op_when_the_bucket_already_exists():
    client = MagicMock()
    client.head_bucket.return_value = {}

    storage.ensure_bucket(client)

    client.head_bucket.assert_called_once_with(Bucket=storage.BUCKET_NAME)
    client.create_bucket.assert_not_called()


def test_ensure_bucket_creates_the_bucket_when_it_does_not_exist_yet():
    client = MagicMock()
    client.head_bucket.side_effect = Exception("404 Not Found")

    storage.ensure_bucket(client)

    client.create_bucket.assert_called_once_with(Bucket=storage.BUCKET_NAME)


# --- put_object -----------------------------------------------------------------


def test_put_object_ensures_the_bucket_then_stores_the_bytes_with_content_type(monkeypatch):
    client = MagicMock()
    client.head_bucket.side_effect = Exception("not found")
    monkeypatch.setattr(storage, "get_client", lambda: client)

    storage.put_object("some/key.txt", b"hello world", "text/plain")

    client.create_bucket.assert_called_once_with(Bucket=storage.BUCKET_NAME)
    client.put_object.assert_called_once_with(
        Bucket=storage.BUCKET_NAME,
        Key="some/key.txt",
        Body=b"hello world",
        ContentType="text/plain",
    )


def test_put_object_skips_bucket_creation_when_the_bucket_already_exists(monkeypatch):
    client = MagicMock()
    client.head_bucket.return_value = {}
    monkeypatch.setattr(storage, "get_client", lambda: client)

    storage.put_object("key.txt", b"data", "text/plain")

    client.create_bucket.assert_not_called()
    client.put_object.assert_called_once_with(
        Bucket=storage.BUCKET_NAME,
        Key="key.txt",
        Body=b"data",
        ContentType="text/plain",
    )


# --- delete_object --------------------------------------------------------------


def test_delete_object_calls_the_client_with_the_bucket_and_given_key(monkeypatch):
    client = MagicMock()
    monkeypatch.setattr(storage, "get_client", lambda: client)

    storage.delete_object("some/key.txt")

    client.delete_object.assert_called_once_with(Bucket=storage.BUCKET_NAME, Key="some/key.txt")


def test_delete_object_swallows_a_client_error_instead_of_raising(monkeypatch):
    """The docstring's contract: 'failures here must not block the row
    delete'. A caller deleting a document row must never have that delete
    aborted by an exception bubbling out of here."""
    client = MagicMock()
    client.delete_object.side_effect = Exception("network error")
    monkeypatch.setattr(storage, "get_client", lambda: client)

    storage.delete_object("some/key.txt")  # must not raise

    client.delete_object.assert_called_once_with(Bucket=storage.BUCKET_NAME, Key="some/key.txt")


def test_delete_object_swallows_a_missing_object_error_too(monkeypatch):
    client = MagicMock()
    client.delete_object.side_effect = Exception("NoSuchKey")
    monkeypatch.setattr(storage, "get_client", lambda: client)

    storage.delete_object("never-existed.txt")  # must not raise
