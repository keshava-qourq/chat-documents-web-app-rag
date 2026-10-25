<!-- sdlc:auto:start adr -->
# ADR-0003: Use PostgreSQL 16 for Database

Status: Accepted  
Date: 2026-10-16

## Context and Problem Statement

Which Database technology does the project use? Decided in architecture v1.

## Considered Options

- PostgreSQL 16
- MySQL
- SQLite

## Decision Outcome

Chosen option: PostgreSQL 16, because One database holds document records, chunks, pgvector embeddings and shared threads/messages, so deleting a document removes its vectors in the same transaction and there is no second system to keep in sync. Similarity search over a few thousand chunks is fast.

## Consequences

pgvector at very large scale lags dedicated vector DBs, but is ideal for hundreds of documents here.
<!-- sdlc:auto:end adr -->