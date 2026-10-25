# Development

> Maintained by QuorQ AI SDLC. Text between `sdlc:auto` markers is regenerated; anything outside them is yours and is kept.

<!-- sdlc:auto:start narrative -->
### DEV-PLAN-V1 · approved · source: plan:version-1

Approved development plan (v1): 6 sprints, capacity 20 each, covering foundation/upload, background indexing, document lifecycle & threads, core grounded chat, chat experience & protection, and launch readiness.

Sprint 1 - Foundation & Upload: open-access app shell, responsive two-area layout, multi-file document upload with validation. Sprint 2 - Background Indexing: server-side extraction, chunking, Gemini embedding pipeline with visible progress/failure and document cap. Sprint 3 - Document Lifecycle & Threads: safe deletion plus shared thread list/creation/auto-titling/rename/delete. Sprint 4 - Core Grounded Chat: retrieval-grounded Q&A strictly from documents with citations and not-found response. Sprint 5 - Chat Experience & Protection: expandable citation excerpts, token-by-token streaming, follow-up context handling, per-IP rate limiting. Sprint 6 - Launch Readiness: operator setup documentation, API key safety checks, billing-free interface confirmation.

**Related:** EPIC-001, EPIC-002, EPIC-003, EPIC-004, EPIC-005

- ⚠ No sprint dates provided.

### DEV-SPRINT-1 · approved · source: plan:SPRINT-1

Sprint 1 - Foundation & Upload. Goal: open-access app shell, responsive two-area layout, multi-file document upload with validation. Capacity 20.

Foundation sprint establishing the open-access shell, responsive two-area layout, and validated multi-file upload. Associated items: EPIC-001, US-001 (Upload documents from the browser, 8 pts, backend-agent) with tasks US-001-T1 build POST /documents endpoint, US-001-T2 integrate MinIO storage client, US-001-T3 build frontend upload component, US-001-T4 test batch upload with partial failure.

**Related:** DEV-PLAN-V1, US-001, US-018

### DEV-SPRINT-2 · approved · source: plan:SPRINT-2

Sprint 2 - Background Indexing. Goal: server-side extraction, chunking and Gemini embedding pipeline with visible progress/failure states and a document cap. Capacity 20.

Implements the background indexing pipeline. Associated items: US-002 (Extract, chunk and embed in background, 8 pts, backend-agent) with tasks US-002-T1 text extraction, US-002-T2 overlapping chunking, US-002-T3 Gemini embeddings with retry, US-002-T4 orchestrate background processing, US-002-T5 test pipeline failure/retry/cleanup. US-003 (See processing progress and failures, 5 pts, backend-agent) with tasks US-003-T1 detailed status endpoint, US-003-T2 frontend status polling, US-003-T3 display processing/failure states in UI.

**Related:** DEV-PLAN-V1, US-002, US-003, US-006

### DEV-SPRINT-3 · approved · source: plan:SPRINT-3

Sprint 3 - Document Lifecycle & Threads. Goal: safe document deletion plus shared conversation thread list, creation, auto-titling, rename and delete. Capacity 20.

Covers document library, deletion, cap, and thread management. Associated items: US-004 (Browse shared library, 5 pts, backend-agent) tasks US-004-T1 GET /documents, US-004-T2 document library UI, US-004-T3 test shared-list visibility. US-005 (Delete document, 5 pts, backend-agent) tasks US-005-T1 DELETE /documents/{id}, US-005-T2 cancel in-flight indexing on delete, US-005-T3 delete confirmation UI, US-005-T4 test deleted-document exclusion from chat. US-006 (Enforce document cap, 3 pts, backend-agent) tasks US-006-T1 cap check, US-006-T2 library-full error UI, US-006-T3 configurable cap with documented default (devops-agent). US-013 (See shared thread list, 3 pts, backend-agent) tasks US-013-T1 GET /threads, US-013-T2 sidebar thread list UI. US-014 (Start/open/continue any thread, 5 pts, backend-agent) tasks US-014-T1 POST /threads and GET /threads/{id}, US-014-T2 new-conversation and open-thread UI, US-014-T3 persist appended messages, US-014-T4 test cross-device persistence. US-015 (Auto-title from first question, 2 pts, backend-agent) tasks US-015-T1 generate auto-title, US-015-T2 truncate title display. US-016 (Rename or delete any thread, 3 pts, backend-agent) tasks US-016-T1 PATCH and DELETE /threads/{id}, US-016-T2 rename/delete UI controls, US-016-T3 reset chat view on active-thread delete.

**Related:** DEV-PLAN-V1, US-004, US-005, US-006, US-013, US-014, US-015, US-016

### DEV-SPRINT-4 · approved · source: plan:SPRINT-4

Sprint 4 - Core Grounded Chat. Goal: retrieval-grounded Q&A strictly from documents, with source citations and a reliable not-found response. Capacity 20.

Implements core grounded chat. Associated items: US-007 (Ask a question answered only from documents, 8 pts, backend-agent) tasks US-007-T1 vector similarity retrieval, US-007-T2 grounded prompt construction, US-007-T3 Gemini generation call, US-007-T4 handle no-ready-documents case, US-007-T5 test Gemini error/timeout handling. US-008 (Say when answer not in documents, 5 pts, backend-agent) tasks US-008-T1 relevance-threshold check, US-008-T2 partial-coverage answering, US-008-T3 test grounding edge cases. US-009 (See source citations, 5 pts, backend-agent) tasks US-009-T1 attach source metadata to citations, US-009-T2 de-duplicate citations per answer, US-009-T3 citation list UI.

**Related:** DEV-PLAN-V1, US-007, US-008, US-009

### DEV-SPRINT-5 · approved · source: plan:SPRINT-5

Sprint 5 - Chat Experience & Protection. Goal: expandable citation excerpts, token-by-token streaming, follow-up context handling and per-IP rate limiting. Capacity 20.

Implements chat experience refinements and abuse protection. Associated items: US-010 (Expand citation to read excerpt, 3 pts, frontend-agent) tasks US-010-T1 expandable citation component, US-010-T2 handle deleted-source citation case. US-011 (Watch answers stream token by token, 5 pts, integration-agent) tasks US-011-T1 server-side streaming, US-011-T2 persist completed message on stream end, US-011-T3 token-by-token frontend rendering, US-011-T4 handle dropped-connection recovery. US-012 (Ask follow-up questions in context, 5 pts, backend-agent) tasks US-012-T1 include prior turns in follow-up context, US-012-T2 context-window truncation, US-012-T3 test reference resolution and thread isolation. US-019 (Rate limit chat and upload per IP, 5 pts, backend-agent) tasks US-019-T1 per-IP rate limiting middleware, US-019-T2 configurable limit settings, US-019-T3 429 handling in frontend, US-019-T4 test limit reset behaviour.

**Related:** DEV-PLAN-V1, US-010, US-011, US-012, US-019

### DEV-SPRINT-6 · approved · source: plan:SPRINT-6

Sprint 6 - Launch Readiness. Goal: operator setup documentation, API key safety checks and confirmation of a billing-free interface. Capacity 20.

Launch readiness sprint. Associated items: US-020 (Configure and run app with Gemini key, 5 pts, devops-agent) tasks US-020-T1 write setup notes, US-020-T2 add startup key validation, US-020-T3 verify key never reaches client, US-020-T4 run clean-environment walkthrough. US-021 (Run as free internal tool with no billing, 1 pt, frontend-agent) task US-021-T1 audit UI for billing elements. US-017 (Use app with no login/password, 1 pt, backend-agent) tasks US-017-T1 confirm no auth gating, US-017-T2 verify shared access across sessions.

**Related:** DEV-PLAN-V1, US-020, US-021, US-017

### DEV-US-020 · approved · source: dev:US-020

Ticket US-020 (Configure and run the app with a Gemini API key) delivered. Commit 70cc5a3c66b43d70d1a8757143a530d267402b33.

Status: delivered. Commit: 70cc5a3c66b43d70d1a8757143a530d267402b33. Covers setup notes, startup key validation, key-never-reaches-client verification, and clean-environment walkthrough.

**Related:** US-020, US-020-T1, US-020-T2, US-020-T3, US-020-T4, DEV-SPRINT-6

- ⚠ No per-task completion breakdown provided; only story-level delivery recorded.

### DEV-US-021 · approved · source: dev:US-021

Ticket US-021 (Run as a free internal tool with no billing) delivered. Commit 70cc5a3c66b43d70d1a8757143a530d267402b33.

Status: delivered. Commit: 70cc5a3c66b43d70d1a8757143a530d267402b33. Covers UI audit for billing elements.

**Related:** US-021, US-021-T1, DEV-SPRINT-6

- ⚠ No per-task completion breakdown provided; only story-level delivery recorded.
<!-- sdlc:auto:end narrative -->
