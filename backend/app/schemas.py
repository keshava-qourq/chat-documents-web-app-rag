"""Pydantic request and response models.

One pair per entity in the approved data model -- documents, chunks (surfaced
through citations), threads, messages and citations -- shaped to match the
approved API spec exactly, plus the placeholder every generated route returns
until it has been implemented.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StubResponse(BaseModel):
    """What a generated route returns until someone implements it.

    A stub that returns a typed body rather than raising keeps the service
    startable and its OpenAPI document complete, so the frontend can be built
    against the agreed shape while the handlers are still being written.
    """

    endpoint: str
    status: str = "not_implemented"
    detail: str = "Scaffolded from the approved API spec; no behaviour yet."


# --- documents ---------------------------------------------------------------


class DocumentAccepted(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_name: str
    size_bytes: int
    mime_type: str
    status: str
    uploaded_at: datetime


class DocumentRejected(BaseModel):
    file_name: str
    reason: str


class UploadResponse(BaseModel):
    accepted: list[DocumentAccepted]
    rejected: list[DocumentRejected]


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    file_name: str
    size_bytes: int
    uploaded_at: datetime
    status: str
    failure_reason: str | None = None
    chunk_count: int


class DocumentStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    progress: int
    failure_reason: str | None = None


# --- threads and messages -----------------------------------------------------


class ThreadSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    last_active_at: datetime


class ThreadCreated(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime


class ThreadRenameRequest(BaseModel):
    title: str = Field(min_length=1)


class ThreadRenameResponse(BaseModel):
    id: uuid.UUID
    title: str


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_name: str
    source_location: str | None = None
    excerpt: str
    # Derived from the persisted `Citation.chunk_id` -- `NULL` once the
    # backing chunk (or its whole document) has since been deleted, via the
    # model's `ondelete="SET NULL"`. Not an ORM attribute, so routes build
    # this explicitly with `from_citation` rather than relying on
    # `from_attributes` to find it on the `Citation` row.
    document_available: bool = True

    @classmethod
    def from_citation(cls, citation: Any) -> "CitationOut":
        return cls(
            id=citation.id,
            document_name=citation.document_name,
            source_location=citation.source_location,
            excerpt=citation.excerpt,
            document_available=citation.chunk_id is not None,
        )


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    status: str
    citations: list[CitationOut] = []


class ThreadDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    messages: list[MessageOut] = []


class MessageCreateRequest(BaseModel):
    question: str = Field(min_length=1)


class MessageStreamFinal(BaseModel):
    """The final SSE event `POST /threads/{id}/messages` sends after its
    streamed tokens, once the answer and its de-duplicated citations are
    persisted."""

    message_id: uuid.UUID
    citations: list[CitationOut] = []
