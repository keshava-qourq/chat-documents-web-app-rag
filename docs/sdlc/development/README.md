# Development

> Maintained by QuorQ AI SDLC. Text between `sdlc:auto` markers is regenerated; anything outside them is yours and is kept.

<!-- sdlc:auto:start narrative -->
### PLAN-V3 · approved · source: plan

Development plan approved at version 3, organized into six sprints taking the app from shell/upload through launch readiness.

Sprint 1 - Foundation & Upload (capacity 20): open-access app shell, responsive two-area layout, multi-file upload with validation. Sprint 2 - Background Indexing (capacity 20): server-side extraction, chunking, Gemini embedding pipeline with visible progress/failure states and a document cap. Sprint 3 - Document Lifecycle & Threads (capacity 20): safe document deletion plus shared conversation thread list, creation, auto-titling, rename and delete. Sprint 4 - Core Grounded Chat (capacity 20): retrieval-grounded Q&A strictly from documents, with citations and a reliable not-found response. Sprint 5 - Chat Experience & Protection (capacity 20): expandable citation excerpts, token-by-token streaming, follow-up context handling, per-IP rate limiting. Sprint 6 - Launch Readiness (capacity 20): operator setup docs, API key safety checks, confirmation of a billing-free interface.

**Related:** US-001, US-002, US-003, US-004, US-005, US-006, US-007, US-008, US-009, US-010, US-011, US-012, US-013, US-014, US-015, US-016, US-017, US-018, US-019, US-020, US-021, US-022, US-023, US-024

- ⚠ Input does not state which individual stories/tasks were assigned to which sprint, so sprint-to-story mapping above is inferred only from goal wording, not explicit assignment.

### EPIC-001 · approved · source: plan:EPIC-001

Epic: Document upload and background indexing.

US-001 Upload documents from the browser (8 pts, backend-agent): POST /documents endpoint, MinIO storage integration, frontend upload component, batch-upload partial-failure test. US-002 Extract, chunk and embed uploaded text in the background (8 pts, backend-agent): text extraction, overlapping chunking, Gemini embeddings with retry (integration-agent), background orchestration, pipeline failure/retry/cleanup test. US-003 See processing progress and failures (5 pts, backend-agent): detailed status endpoint, frontend status polling, UI display of processing/failure states.

**Related:** US-001, US-002, US-003

- ⚠ No development run record provided confirming these stories were actually built; only planning data is available.

### EPIC-002 · approved · source: plan:EPIC-002

Epic: Shared document library.

US-004 Browse the shared document library (5 pts, backend-agent): GET /documents endpoint, document library UI, shared-list visibility test. US-005 Delete a document and remove it from the index (5 pts, backend-agent): DELETE /documents/{id}, cancel in-flight indexing on delete, delete confirmation UI, test for deleted-document exclusion from chat. US-006 Enforce a cap on total stored documents (3 pts, backend-agent): document cap check, library-full error surfaced in UI, configurable cap with documented default (devops-agent).

**Related:** US-004, US-005, US-006

- ⚠ No development run record provided confirming these stories were actually built; only planning data is available.

### EPIC-003 · approved · source: plan:EPIC-003

Epic: Grounded chat with citations.

US-007 Ask a question answered only from the documents (8 pts, backend-agent): vector similarity retrieval, grounded prompt construction, Gemini generation call (integration-agent), handling of no-ready-documents case, test of Gemini error/timeout handling. US-008 Say when the answer is not in the documents (5 pts, backend-agent): relevance-threshold check, partial-coverage answering, grounding edge-case tests. US-009 See source citations on every answer (5 pts, backend-agent): source metadata attached to citations, citation de-duplication, citation list UI (frontend-agent). US-010 Expand a citation to read the retrieved excerpt (3 pts, frontend-agent): expandable citation component, handling of deleted-source citation case (backend-agent). US-011 Watch answers stream in token by token (5 pts, integration-agent): server-side streaming, persisting completed message on stream end, token-by-token frontend rendering, dropped-connection recovery test. US-012 Ask follow-up questions in context (5 pts, backend-agent): prior turns included in follow-up context, context-window truncation, reference-resolution/thread-isolation test.

**Related:** US-007, US-008, US-009, US-010, US-011, US-012

- ⚠ No development run record provided confirming these stories were actually built; only planning data is available.

### EPIC-004 · approved · source: plan:EPIC-004

Epic: Shared conversation history.

US-013 See the shared list of conversation threads (3 pts, backend-agent): GET /threads, sidebar thread list UI. US-014 Start, open and continue any thread (5 pts, backend-agent): POST /threads and GET /threads/{id}, new-conversation/open-thread UI, persisting appended messages to the shared thread, cross-device persistence test. US-015 Auto-title a thread from its first question (2 pts, backend-agent): auto-title generation, truncated title display in sidebar (frontend-agent). US-016 Rename or delete any thread (3 pts, backend-agent): PATCH/DELETE /threads/{id}, rename/delete UI controls, chat view reset on active-thread delete.

**Related:** US-013, US-014, US-015, US-016

- ⚠ No development run record provided confirming these stories were actually built; only planning data is available.

### EPIC-005 · approved · source: plan:EPIC-005

Epic: Open access, abuse protection and operation.

US-017 Use the app with no login or password (1 pt, backend-agent): confirmation of no auth gating, verification of shared access across sessions (qa-agent). US-018 Navigate a responsive two-area layout (5 pts, frontend-agent): two-area responsive shell, mobile breakpoint navigation, light/neutral English-only styling. US-019 Rate limit chat and upload per IP (5 pts, backend-agent): per-IP rate limiting middleware, configurable limit settings (devops-agent), 429 handling in frontend, limit-reset-behaviour test. US-020 Configure and run the app with a Gemini API key (5 pts, devops-agent): setup notes, startup key validation (backend-agent), verification the key never reaches the client (security-agent), clean-environment walkthrough (qa-agent). US-021 Run as a free internal tool with no billing (1 pt, frontend-agent): audit of UI for billing elements.

**Related:** US-017, US-018, US-019, US-020, US-021

- ⚠ No development run record provided confirming these stories were actually built; only planning data is available.

### BACKLOG-UI-POLISH · approved · source: plan

Later backlog items not grouped under any of the five original epics, covering chat bubble alignment and a blue/purple accent color rollout.

US-022 Correct chat message bubble alignment (2 pts, frontend-agent). US-023 Apply blue/purple accent color tokens across the app (3 pts, frontend-agent). US-024 Verify no visual regressions from the new accent color palette (2 pts, qa-agent).

**Related:** US-022, US-023, US-024

- ⚠ These three items are not assigned to an epic in the input; unclear if they belong to an existing epic or are a separate workstream.

### DEV-RUN-COVERAGE · approved · source: dev

_2026-10-25_

Development run status is reported as 'completed', but only two of the 24 planned stories (US-023, US-024) have recorded run/ticket outcomes in this input.

The run-level status field says 'completed' even though the only ticket detail supplied for that run, US-024, is marked 'failed' with no commit -- this is a discrepancy between the overall run status and the individual ticket outcome. No ticket records were supplied for US-001 through US-022, so whether those stories (upload, indexing, library, grounded chat, citations, streaming, threads, rate limiting, API key setup, etc.) were implemented, are in progress, or have not been started cannot be determined from this input.

**Related:** US-023, US-024

- ⚠ Discrepancy: run marked 'completed' while its one reported ticket (US-024) is 'failed' -- needs clarification on what 'completed' refers to.
- ⚠ No run/ticket data provided for US-001 through US-022; their implementation status is undocumented.
- ⚠ No date is given for this development run.

### DEV-TICKET-US-023 · approved · source: dev:TICKET-US-023

Ticket to apply blue/purple accent color tokens across the app was delivered.

Ticket US-023 'Apply blue/purple accent color tokens across the app' -- status: delivered. Commit: f5b7749472b19b456479b1d9bc0939ba89862ae9.

**Related:** US-023

- ⚠ No date of delivery provided.
- ⚠ No description of which specific screens/components received the new tokens.

### DEV-TICKET-US-024 · approved · source: dev:TICKET-US-024

QA verification that the new accent color palette introduced no visual regressions did not pass.

Ticket US-024 'Verify no visual regressions from the new accent color palette' -- status: failed. No commit recorded.

**Related:** US-024, US-023

- ⚠ Reason for failure (which screens/elements regressed) not provided in input.
- ⚠ No remediation plan or re-test status recorded.
- ⚠ Unclear whether US-023's delivered change will be reverted, rolled back, or fixed given this QA failure.
<!-- sdlc:auto:end narrative -->
