"""Thin boto3 wrapper around the MinIO bucket that holds original uploads.

Settings come from the MinIO env vars already present in `.env.example`
(`MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`); nothing new is
introduced. The bucket itself is created on first use if it does not exist
yet, so a fresh `docker compose up` needs no manual setup step.
"""

import os

import boto3
from botocore.client import Config

BUCKET_NAME = os.getenv("MINIO_BUCKET", "documents")


def _endpoint_url() -> str:
    endpoint = os.getenv("MINIO_ENDPOINT", "")
    if not endpoint:
        return ""
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint
    return f"http://{endpoint}"


def get_client():
    """A fresh boto3 S3 client pointed at the configured MinIO endpoint."""
    return boto3.client(
        "s3",
        endpoint_url=_endpoint_url(),
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY"),
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def ensure_bucket(client) -> None:
    """Creates the bucket if it is missing; a no-op once it exists."""
    try:
        client.head_bucket(Bucket=BUCKET_NAME)
    except Exception:
        client.create_bucket(Bucket=BUCKET_NAME)


def put_object(key: str, data: bytes, content_type: str) -> None:
    """Stores one original file's bytes under `key` in the shared bucket."""
    client = get_client()
    ensure_bucket(client)
    client.put_object(Bucket=BUCKET_NAME, Key=key, Body=data, ContentType=content_type)


def delete_object(key: str) -> None:
    """Removes one object; failures here must not block the row delete."""
    client = get_client()
    try:
        client.delete_object(Bucket=BUCKET_NAME, Key=key)
    except Exception:
        pass
