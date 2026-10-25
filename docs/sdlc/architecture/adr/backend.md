<!-- sdlc:auto:start adr -->
# ADR-0002: Use FastAPI 0.115 for Backend

Status: Accepted  
Date: 2026-10-16

## Context and Problem Statement

Which Backend technology does the project use? Decided in architecture v1.

## Considered Options

- FastAPI 0.115
- Django
- Flask

## Decision Outcome

Chosen option: FastAPI 0.115, because Handles multipart uploads, streaming (SSE) answer responses, per-IP rate limiting, and hosts the background indexer in-process so no separate queue is required, while Python's mature libraries extract PDF/DOCX text.

## Consequences

In-process background indexing ties processing to backend uptime and a single instance; sufficient at this scale but not horizontally scalable without a queue.
<!-- sdlc:auto:end adr -->