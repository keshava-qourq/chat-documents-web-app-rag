"""SQLAlchemy models.

One table per entity in the approved data model: documents, chunks, threads,
messages and citations. `Base` is already bound to the engine and `main.py`
imports this module before it creates the schema.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, ForeignKey, Integer, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, DateTime, TypeDecorator

from app.database import Base

# Gemini's gemini-embedding-001, the model this project calls for embeddings,
# is asked for 768-dimensional vectors; chunks.embedding is sized to match.
EMBEDDING_DIM = 768


class EmbeddingVector(TypeDecorator):
    """`vector(768)` on Postgres, a plain JSON array everywhere else.

    The approved architecture stores embeddings in pgvector, but
    `database.py` defaults to SQLite so a fresh clone runs with nothing but
    `pip install -r requirements.txt` -- and SQLite has no vector type. This
    column degrades to JSON there and becomes the real pgvector column the
    moment `DATABASE_URL` points at Postgres; nothing that reads or writes it
    has to change either way.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(Vector(EMBEDDING_DIM))
        return dialect.type_descriptor(JSON())


class Document(Base):
    """One uploaded file and where its indexing stands."""

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="processing")
    # Updated as the ingestion pipeline embeds each batch of chunks, so a
    # poller sees indexing advance rather than jumping straight from 0 to
    # done. Additive column -- existing rows default to 0 either way.
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )


class Chunk(Base):
    """One retrieval-sized slice of a document, with its embedding."""

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(EmbeddingVector, nullable=True)

    document: Mapped[Document] = relationship(back_populates="chunks")
    citations: Mapped[list["Citation"]] = relationship(back_populates="chunk")


class Thread(Base):
    """A shared conversation; every visitor sees the same list."""

    __tablename__ = "threads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(Text, nullable=False, default="New conversation")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
    )


class Message(Base):
    """One turn in a thread -- a question or a generated answer."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(Text, nullable=False, default="complete")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    thread: Mapped[Thread] = relationship(back_populates="messages")
    citations: Mapped[list["Citation"]] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
    )


class Citation(Base):
    """One source a generated answer points back to."""

    __tablename__ = "citations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("chunks.id", ondelete="SET NULL"),
        nullable=True,
    )
    document_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)

    message: Mapped[Message] = relationship(back_populates="citations")
    chunk: Mapped[Chunk | None] = relationship(back_populates="citations")


__all__ = [
    "Base",
    "Document",
    "Chunk",
    "Thread",
    "Message",
    "Citation",
    "EmbeddingVector",
    "EMBEDDING_DIM",
]
