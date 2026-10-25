<!-- sdlc:auto:start adr -->
# ADR-0001: Use React 19 for Frontend

Status: Accepted  
Date: 2026-10-16

## Context and Problem Statement

Which Frontend technology does the project use? Decided in architecture v1.

## Considered Options

- React 19
- Vue
- Svelte

## Decision Outcome

Chosen option: React 19, because Builds the responsive two-area layout (chat with thread sidebar plus documents screen), consumes the SSE token stream for progressive answers, and polls document status for live indexing progress.

## Consequences

A SPA requires client-side state for streaming and polling; acceptable given the small, focused UI and no SEO needs.
<!-- sdlc:auto:end adr -->