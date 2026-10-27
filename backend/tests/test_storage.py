"""Unit tests for `app/storage.py`.

This ticket ("Unit tests for backend/app/storage.py") carries no acceptance
criteria of its own, so tests are named for the behaviour they pin down
rather than an AC id.

`storage.py` is the thin boundary between this app and the project's own
MinIO bucket -- every other suite in this repository replaces it with the
`fake_object_store` fixture from `conftest.py` precisely so the rest of the
app can be tested without a live object store. This file is the one place
that is *about* that boundary itself, so it exercises the real thing: MinIO
is one of this project's own services, always running alongside the
database, and its connection settings (`MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`,
`MINIO_SECRET_KEY`) are already set in this environment -- so these tests
read them the same way `storage.py` does, rather than mocking boto3 out from
under the module under test.

Every test that creates or writes an object does so under a throwaway,
randomly-named bucket (via the `test_bucket` fixture, which reloads the
module with its own `MINIO_BUCKET` and restores it afterwards -- the same
reload-and-restore shape `test_database.py` uses for its own env-driven
module-level state), so none of these tests touch the `documents` bucket the
running application itself reads and writes.
"""

import importlib
import os
import uuid

import pytest
from botocore.exceptions import ClientError

from app import storage


# --- _endpoint_url: pure formatting, no network needed -----------------------


def test_endpoint_url_is_empty_when_minio_endpoint_unset(monkeypatch):
    monkeypatch.delenv("MINIO_ENDPOINT", raising=False)

    assert storage._endpoint_url() == ""


def test_endpoint_url_adds_http_scheme_to_a_bare_host_and_port(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")

    assert storage._endpoint_url() == "http://minio:9000"


def test_endpoint_url_leaves_an_explicit_http_scheme_untouched(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "http://minio:9000")

    assert storage._endpoint_url() == "http://minio:9000"


def test_endpoint_url_leaves_an_explicit_https_scheme_untouched(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "https://s3.example.com")

    assert storage._endpoint_url() == "https://s3.example.com"


# --- get_client: built from the configured endpoint, no network needed ------


def test_get_client_targets_the_configured_minio_endpoint(monkeypatch):
    monkeypatch.setenv("MINIO_ENDPOINT", "minio:9000")

    client = storage.get_client()

    assert client.meta.endpoint_url == "http://minio:9000"
    assert client.meta.region_name == "us-east-1"


# --- BUCKET_NAME: module-level constant, read once at import ----------------


@pytest.fixture()
def _restore_storage_module():
    """`BUCKET_NAME` in `app.storage` is computed once at import time, not
    re-read per call, so a test that reloads the module under a different
    `MINIO_BUCKET` leaves it in that state for the rest of the process
    unless something puts it back. Mirrors `test_database.py`'s
    `_restore_database_module` fixture for the same reason: every other
    module here does `from app import storage` and keeps using the shared
    module object, so a reload this file leaves in place would otherwise
    leak into every other suite that runs afterwards."""
    original = os.environ.get("MINIO_BUCKET")
    try:
        yield
    finally:
        if original is None:
            os.environ.pop("MINIO_BUCKET", None)
        else:
            os.environ["MINIO_BUCKET"] = original
        importlib.reload(storage)


def test_bucket_name_defaults_to_documents_when_minio_bucket_unset(monkeypatch, _restore_storage_module):
    monkeypatch.delenv("MINIO_BUCKET", raising=False)

    reloaded = importlib.reload(storage)

    assert reloaded.BUCKET_NAME == "documents"


def test_bucket_name_reads_minio_bucket_env_override(monkeypatch, _restore_storage_module):
    monkeypatch.setenv("MINIO_BUCKET", "a-different-bucket")

    reloaded = importlib.reload(storage)

    assert reloaded.BUCKET_NAME == "a-different-bucket"


# --- ensure_bucket / put_object / delete_object: against the real MinIO -----


@pytest.fixture()
def test_bucket():
    """Points `storage.BUCKET_NAME` at a freshly-named, empty bucket for the
    duration of one test, so these tests never read or write the shared
    `documents` bucket the running application itself uses, and restores the
    module to whatever `MINIO_BUCKET` it had before once the test is done."""
    bucket_name = f"storage-test-{uuid.uuid4().hex}"
    original = os.environ.get("MINIO_BUCKET")
    os.environ["MINIO_BUCKET"] = bucket_name
    reloaded = importlib.reload(storage)
    try:
        yield reloaded
    finally:
        if original is None:
            os.environ.pop("MINIO_BUCKET", None)
        else:
            os.environ["MINIO_BUCKET"] = original
        importlib.reload(storage)


def test_ensure_bucket_creates_the_bucket_when_it_does_not_exist_yet(test_bucket):
    client = test_bucket.get_client()
    with pytest.raises(ClientError):
        client.head_bucket(Bucket=test_bucket.BUCKET_NAME)

    test_bucket.ensure_bucket(client)

    client.head_bucket(Bucket=test_bucket.BUCKET_NAME)  # no longer raises


def test_ensure_bucket_is_a_no_op_once_the_bucket_already_exists(test_bucket):
    client = test_bucket.get_client()
    test_bucket.ensure_bucket(client)

    test_bucket.ensure_bucket(client)  # must not raise calling it a second time

    client.head_bucket(Bucket=test_bucket.BUCKET_NAME)


def test_put_object_stores_bytes_retrievable_with_the_given_content_type(test_bucket):
    key = f"docs/{uuid.uuid4().hex}.txt"

    test_bucket.put_object(key, b"hello world", "text/plain")

    client = test_bucket.get_client()
    response = client.get_object(Bucket=test_bucket.BUCKET_NAME, Key=key)
    assert response["Body"].read() == b"hello world"
    assert response["ContentType"] == "text/plain"


def test_put_object_creates_the_bucket_itself_when_it_does_not_exist_yet(test_bucket):
    """`put_object` must not require a separate setup step first -- a fresh
    environment with no bucket at all still accepts the very first upload,
    which is what makes a fresh `docker compose up` need no manual step."""
    client = test_bucket.get_client()
    with pytest.raises(ClientError):
        client.head_bucket(Bucket=test_bucket.BUCKET_NAME)

    test_bucket.put_object("first-upload.txt", b"data", "text/plain")

    client.head_bucket(Bucket=test_bucket.BUCKET_NAME)  # no longer raises


def test_delete_object_removes_a_previously_stored_object(test_bucket):
    key = f"docs/{uuid.uuid4().hex}.txt"
    test_bucket.put_object(key, b"to be deleted", "text/plain")
    client = test_bucket.get_client()

    test_bucket.delete_object(key)

    with pytest.raises(ClientError):
        client.get_object(Bucket=test_bucket.BUCKET_NAME, Key=key)


def test_delete_object_does_not_raise_for_a_key_that_was_never_stored(test_bucket):
    """The module's own docstring says failures here must not block the row
    delete -- deleting a key that is already gone (or never existed) in an
    otherwise-real bucket is exactly that case."""
    test_bucket.ensure_bucket(test_bucket.get_client())

    test_bucket.delete_object("never-existed.txt")  # must not raise


def test_delete_object_swallows_an_error_from_a_bucket_that_does_not_exist(test_bucket):
    """Covers the actual `except Exception: pass` in `delete_object` against
    a failure from the client call itself, not just a missing key in a
    bucket that exists: the bucket here was never created."""
    test_bucket.delete_object("whatever.txt")  # must not raise
