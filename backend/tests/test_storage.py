"""Unit tests for `app.storage`: the boto3/MinIO wrapper around the shared
object store that holds original uploads.

No test here ever opens a real network connection to MinIO. `get_client`'s
own boto3 call is exercised by monkeypatching `boto3.client` (via the
module's own `storage.boto3` reference) to capture what it was called with,
and `ensure_bucket`/`put_object`/`delete_object` are each exercised against
a small fake client object standing in for what `get_client` would
otherwise hand back -- the same substitution `conftest.py`'s
`fake_object_store` fixture makes for every other suite that uses this
module indirectly.
"""

import importlib
import os

import pytest
from botocore.client import Config

from app import storage

# --- BUCKET_NAME: resolved once at import time from MINIO_BUCKET ----------


@pytest.fixture()
def _restore_storage_module():
    """`BUCKET_NAME` is computed once at import time from `MINIO_BUCKET`, so
    exercising an overridden value means reloading the module under a
    controlled environment -- restored here by reloading again with
    `MINIO_BUCKET` unset, leaving every other test in this file (and every
    other suite's `from app import storage`) pointed at the documented
    default, exactly as it was before this fixture's test ran.
    """
    yield
    os.environ.pop("MINIO_BUCKET", None)
    importlib.reload(storage)


def test_bucket_name_defaults_to_documents_when_unset(monkeypatch, _restore_storage_module) -> None:
    monkeypatch.delenv("MINIO_BUCKET", raising=False)

    importlib.reload(storage)

    assert storage.BUCKET_NAME == "documents"


def test_bucket_name_reads_an_overridden_value(monkeypatch, _restore_storage_module) -> None:
    monkeypatch.setenv("MINIO_BUCKET", "custom-bucket")

    importlib.reload(storage)

    assert storage.BUCKET_NAME == "custom-bucket"


# --- _endpoint_url -----------------------------------------------------


def test_endpoint_url_is_empty_string_when_minio_endpoint_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)

    assert storage._endpoint_url() == ""


def test_endpoint_url_prefixes_a_bare_host_with_http(monkeypatch) -> None:
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")

    assert storage._endpoint_url() == "http://minio:9000"


def test_endpoint_url_leaves_an_explicit_http_scheme_untouched(monkeypatch) -> None:
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")

    assert storage._endpoint_url() == "http://minio:9000"


def test_endpoint_url_leaves_an_explicit_https_scheme_untouched(monkeypatch) -> None:
    monkeypatch.setenv("MINIO_ENDPOINT", "https://minio.example.com")

    assert storage._endpoint_url() == "https://minio.example.com"


# --- get_client: builds a boto3 S3 client from the MinIO env vars ---------


def test_get_client_passes_the_configured_endpoint_and_credentials_to_boto3(monkeypatch) -> None:
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "the-access-key")
    monkeypatch.setenv("MINIO_SECRET_KEY", "the-secret-key")

    captured = {}

    def fake_boto3_client(service_name, **kwargs):
        captured["service_name"] = service_name
        captured.update(kwargs)
        return "fake-client"

    monkeypatch.setattr(storage.boto3, "client", fake_boto3_client)

    result = storage.get_client()

    assert result == "fake-client"
    assert captured["service_name"] == "s3"
    assert captured["endpoint_url"] == "http://minio:9000"
    assert captured["aws_access_key_id"] == "the-access-key"
    assert captured["aws_secret_access_key"] == "the-secret-key"
    assert captured["region_name"] == "us-east-1"
    assert isinstance(captured["config"], Config)
    assert captured["config"].signature_version == "s3v4"


def test_get_client_builds_a_fresh_client_on_every_call(monkeypatch) -> None:
    """`put_object`/`delete_object` each call `get_client()` fresh rather
    than caching a client module-wide -- a cached client would silently keep
    using whichever endpoint/credentials were current the moment it was
    first built, ignoring any later change to the MinIO env vars."""
    calls = {"count": 0}

    def fake_boto3_client(service_name, **kwargs):
        calls["count"] += 1
        return object()

    monkeypatch.setattr(storage.boto3, "client", fake_boto3_client)

    first = storage.get_client()
    second = storage.get_client()

    assert calls["count"] == 2
    assert first is not second


# --- ensure_bucket ----------------------------------------------------


class _FakeClientBucketExists:
    def __init__(self) -> None:
        self.create_bucket_calls: list[str] = []

    def head_bucket(self, Bucket):  # noqa: N803 -- matches boto3's signature
        return {}

    def create_bucket(self, Bucket):  # noqa: N803
        self.create_bucket_calls.append(Bucket)


class _FakeClientBucketMissing:
    def __init__(self) -> None:
        self.create_bucket_calls: list[str] = []

    def head_bucket(self, Bucket):  # noqa: N803
        raise Exception("404 Not Found")

    def create_bucket(self, Bucket):  # noqa: N803
        self.create_bucket_calls.append(Bucket)


def test_ensure_bucket_is_a_no_op_when_the_bucket_already_exists() -> None:
    client = _FakeClientBucketExists()

    storage.ensure_bucket(client)

    assert client.create_bucket_calls == []


def test_ensure_bucket_creates_the_bucket_when_head_bucket_raises() -> None:
    client = _FakeClientBucketMissing()

    storage.ensure_bucket(client)

    assert client.create_bucket_calls == [storage.BUCKET_NAME]


# --- put_object --------------------------------------------------------


class _RecordingClient:
    def __init__(self, bucket_exists: bool = True) -> None:
        self.bucket_exists = bucket_exists
        self.create_bucket_calls: list[str] = []
        self.put_object_calls: list[tuple] = []
        self.delete_object_calls: list[tuple] = []
        self.delete_object_raises = False

    def head_bucket(self, Bucket):  # noqa: N803
        if not self.bucket_exists:
            raise Exception("404 Not Found")

    def create_bucket(self, Bucket):  # noqa: N803
        self.create_bucket_calls.append(Bucket)

    def put_object(self, Bucket, Key, Body, ContentType):  # noqa: N803
        self.put_object_calls.append((Bucket, Key, Body, ContentType))

    def delete_object(self, Bucket, Key):  # noqa: N803
        self.delete_object_calls.append((Bucket, Key))
        if self.delete_object_raises:
            raise Exception("simulated MinIO failure")


def test_put_object_creates_a_missing_bucket_then_stores_the_bytes_under_the_key(
    monkeypatch,
) -> None:
    client = _RecordingClient(bucket_exists=False)
    monkeypatch.setattr(storage, "get_client", lambda: client)

    storage.put_object("some/key.txt", b"hello world", "text/plain")

    assert client.create_bucket_calls == [storage.BUCKET_NAME]
    expected = (storage.BUCKET_NAME, "some/key.txt", b"hello world", "text/plain")
    assert client.put_object_calls == [expected]


def test_put_object_does_not_create_the_bucket_when_it_already_exists(monkeypatch) -> None:
    client = _RecordingClient(bucket_exists=True)
    monkeypatch.setattr(storage, "get_client", lambda: client)

    storage.put_object("key.txt", b"data", "text/plain")

    assert client.create_bucket_calls == []
    assert client.put_object_calls == [(storage.BUCKET_NAME, "key.txt", b"data", "text/plain")]


# --- delete_object -------------------------------------------------------


def test_delete_object_removes_the_object_under_the_given_key(monkeypatch) -> None:
    client = _RecordingClient()
    monkeypatch.setattr(storage, "get_client", lambda: client)

    storage.delete_object("some/key.txt")

    assert client.delete_object_calls == [(storage.BUCKET_NAME, "some/key.txt")]


def test_delete_object_swallows_a_failure_instead_of_raising(monkeypatch) -> None:
    """The module's own docstring is explicit: a storage failure here must
    not block the row delete it accompanies -- proven by calling it against
    a client whose `delete_object` always raises and confirming nothing
    propagates out of `storage.delete_object` itself."""
    client = _RecordingClient()
    client.delete_object_raises = True
    monkeypatch.setattr(storage, "get_client", lambda: client)

    storage.delete_object("some/key.txt")  # must not raise

    assert client.delete_object_calls == [(storage.BUCKET_NAME, "some/key.txt")]
