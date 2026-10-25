<!-- sdlc:auto:start adr -->
# ADR-0004: Use AWS for Cloud

Status: Accepted  
Date: 2026-10-16

## Context and Problem Statement

Which Cloud technology does the project use? Decided in architecture v1.

## Considered Options

- AWS
- GCP
- Azure

## Decision Outcome

Chosen option: AWS, because Provides managed PostgreSQL with pgvector and object storage under one account and bill on the smallest instances for a small internal tool; the real spend stays on the Gemini key.

## Consequences

Single-account single-instance setup has no built-in HA, acceptable for a lightweight internal tool.
<!-- sdlc:auto:end adr -->