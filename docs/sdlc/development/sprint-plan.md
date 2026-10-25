# Sprint Plan

> Maintained by QuorQ AI SDLC. Text between `sdlc:auto` markers is regenerated; anything outside them is yours and is kept.

<!-- sdlc:auto:start sprints -->
## Sprint 1: Sprint 1 - Foundation & Upload

Open-access app shell, responsive two-area layout, and multi-file document upload with validation

Capacity: 20 points · Committed: 19

| Key | Type | Title | Points | Role | Depends on |
|---|---|---|---|---|---|
| US-001 | Story | Upload documents from the browser | 8 | backend-agent | — |
| ↳ US-001-T1 | Task | Build POST /documents endpoint | — | backend-agent | — |
| ↳ US-001-T2 | Task | Integrate MinIO storage client | — | backend-agent | — |
| ↳ US-001-T3 | Task | Build frontend upload component | — | frontend-agent | — |
| ↳ US-001-T4 | Task | Test batch upload with partial failure | — | qa-agent | — |
| US-004 | Story | Browse the shared document library | 5 | backend-agent | US-001 |
| ↳ US-004-T1 | Task | Implement GET /documents endpoint | — | backend-agent | — |
| ↳ US-004-T2 | Task | Build document library UI | — | frontend-agent | — |
| ↳ US-004-T3 | Task | Test shared-list visibility | — | qa-agent | — |
| US-017 | Story | Use the app with no login or password | 1 | backend-agent | — |
| ↳ US-017-T1 | Task | Confirm no auth gating | — | backend-agent | — |
| ↳ US-017-T2 | Task | Verify shared access across sessions | — | qa-agent | — |
| US-018 | Story | Navigate a responsive two-area layout | 5 | frontend-agent | — |
| ↳ US-018-T1 | Task | Build two-area responsive shell | — | frontend-agent | — |
| ↳ US-018-T2 | Task | Implement mobile breakpoint navigation | — | frontend-agent | — |
| ↳ US-018-T3 | Task | Apply light/neutral English-only styling | — | frontend-agent | — |

## Sprint 2: Sprint 2 - Background Indexing

Server-side extraction, chunking and Gemini embedding pipeline with visible progress/failure states and a document cap

Capacity: 20 points · Committed: 16

| Key | Type | Title | Points | Role | Depends on |
|---|---|---|---|---|---|
| US-002 | Story | Extract, chunk and embed uploaded text in the background | 8 | backend-agent | US-001 |
| ↳ US-002-T1 | Task | Implement text extraction | — | backend-agent | — |
| ↳ US-002-T2 | Task | Implement overlapping chunking | — | backend-agent | — |
| ↳ US-002-T3 | Task | Integrate Gemini embeddings with retry | — | integration-agent | — |
| ↳ US-002-T4 | Task | Orchestrate background processing | — | backend-agent | — |
| ↳ US-002-T5 | Task | Test pipeline failure/retry/cleanup | — | qa-agent | — |
| US-003 | Story | See processing progress and failures | 5 | backend-agent | US-002 |
| ↳ US-003-T1 | Task | Expose detailed status endpoint | — | backend-agent | — |
| ↳ US-003-T2 | Task | Build frontend status polling | — | frontend-agent | — |
| ↳ US-003-T3 | Task | Display processing/failure states in UI | — | frontend-agent | — |
| US-006 | Story | Enforce a cap on total stored documents | 3 | backend-agent | US-001 |
| ↳ US-006-T1 | Task | Add document cap check | — | backend-agent | — |
| ↳ US-006-T2 | Task | Surface library-full error in UI | — | frontend-agent | — |
| ↳ US-006-T3 | Task | Add configurable cap with documented default | — | devops-agent | — |

## Sprint 3: Sprint 3 - Document Lifecycle & Threads

Safe document deletion plus shared conversation thread list, creation, auto-titling, rename and delete

Capacity: 20 points · Committed: 18

| Key | Type | Title | Points | Role | Depends on |
|---|---|---|---|---|---|
| US-005 | Story | Delete a document and remove it from the index | 5 | backend-agent | US-002 |
| ↳ US-005-T1 | Task | Implement DELETE /documents/{id} | — | backend-agent | — |
| ↳ US-005-T2 | Task | Cancel in-flight indexing on delete | — | backend-agent | — |
| ↳ US-005-T3 | Task | Build delete confirmation UI | — | frontend-agent | — |
| ↳ US-005-T4 | Task | Test deleted-document exclusion from chat | — | qa-agent | — |
| US-013 | Story | See the shared list of conversation threads | 3 | backend-agent | — |
| ↳ US-013-T1 | Task | Implement GET /threads | — | backend-agent | — |
| ↳ US-013-T2 | Task | Build sidebar thread list UI | — | frontend-agent | — |
| US-014 | Story | Start, open and continue any thread | 5 | backend-agent | US-013 |
| ↳ US-014-T1 | Task | Implement POST /threads and GET /threads/{id} | — | backend-agent | — |
| ↳ US-014-T2 | Task | Build new-conversation and open-thread UI | — | frontend-agent | — |
| ↳ US-014-T3 | Task | Persist appended messages to shared thread | — | backend-agent | — |
| ↳ US-014-T4 | Task | Test cross-device persistence | — | qa-agent | — |
| US-015 | Story | Auto-title a thread from its first question | 2 | backend-agent | US-014 |
| ↳ US-015-T1 | Task | Generate auto-title from first question | — | backend-agent | — |
| ↳ US-015-T2 | Task | Truncate title display in sidebar | — | frontend-agent | — |
| US-016 | Story | Rename or delete any thread | 3 | backend-agent | US-014 |
| ↳ US-016-T1 | Task | Implement PATCH and DELETE /threads/{id} | — | backend-agent | — |
| ↳ US-016-T2 | Task | Build rename/delete UI controls | — | frontend-agent | — |
| ↳ US-016-T3 | Task | Reset chat view on active-thread delete | — | frontend-agent | — |

## Sprint 4: Sprint 4 - Core Grounded Chat

Retrieval-grounded question answering strictly from documents, with source citations and a reliable not-found response

Capacity: 20 points · Committed: 18

| Key | Type | Title | Points | Role | Depends on |
|---|---|---|---|---|---|
| US-007 | Story | Ask a question answered only from the documents | 8 | backend-agent | US-002, US-014 |
| ↳ US-007-T1 | Task | Implement vector similarity retrieval | — | backend-agent | — |
| ↳ US-007-T2 | Task | Build grounded prompt construction | — | backend-agent | — |
| ↳ US-007-T3 | Task | Integrate Gemini generation call | — | integration-agent | — |
| ↳ US-007-T4 | Task | Handle no-ready-documents case | — | backend-agent | — |
| ↳ US-007-T5 | Task | Test Gemini error/timeout handling | — | qa-agent | — |
| US-008 | Story | Say when the answer is not in the documents | 5 | backend-agent | US-007 |
| ↳ US-008-T1 | Task | Implement relevance-threshold check | — | backend-agent | — |
| ↳ US-008-T2 | Task | Implement partial-coverage answering | — | backend-agent | — |
| ↳ US-008-T3 | Task | Test grounding edge cases | — | qa-agent | — |
| US-009 | Story | See source citations on every answer | 5 | backend-agent | US-007 |
| ↳ US-009-T1 | Task | Attach source metadata to citations | — | backend-agent | — |
| ↳ US-009-T2 | Task | De-duplicate citations per answer | — | backend-agent | — |
| ↳ US-009-T3 | Task | Build citation list UI | — | frontend-agent | — |

## Sprint 5: Sprint 5 - Chat Experience & Protection

Expandable citation excerpts, token-by-token streaming, follow-up context handling and per-IP rate limiting

Capacity: 20 points · Committed: 18

| Key | Type | Title | Points | Role | Depends on |
|---|---|---|---|---|---|
| US-010 | Story | Expand a citation to read the retrieved excerpt | 3 | frontend-agent | US-009 |
| ↳ US-010-T1 | Task | Build expandable citation component | — | frontend-agent | — |
| ↳ US-010-T2 | Task | Handle deleted-source citation case | — | backend-agent | — |
| US-011 | Story | Watch answers stream in token by token | 5 | integration-agent | US-007 |
| ↳ US-011-T1 | Task | Implement server-side streaming | — | integration-agent | — |
| ↳ US-011-T2 | Task | Persist completed message on stream end | — | backend-agent | — |
| ↳ US-011-T3 | Task | Build token-by-token frontend rendering | — | frontend-agent | — |
| ↳ US-011-T4 | Task | Handle dropped-connection recovery | — | qa-agent | — |
| US-012 | Story | Ask follow-up questions in context | 5 | backend-agent | US-007, US-014 |
| ↳ US-012-T1 | Task | Include prior turns in follow-up context | — | backend-agent | — |
| ↳ US-012-T2 | Task | Implement context-window truncation | — | backend-agent | — |
| ↳ US-012-T3 | Task | Test reference resolution and thread isolation | — | qa-agent | — |
| US-019 | Story | Rate limit chat and upload per IP | 5 | backend-agent | US-001, US-007 |
| ↳ US-019-T1 | Task | Implement per-IP rate limiting middleware | — | backend-agent | — |
| ↳ US-019-T2 | Task | Add configurable limit settings | — | devops-agent | — |
| ↳ US-019-T3 | Task | Build 429 handling in frontend | — | frontend-agent | — |
| ↳ US-019-T4 | Task | Test limit reset behaviour | — | qa-agent | — |

## Sprint 6: Sprint 6 - Launch Readiness

Operator setup documentation, API key safety checks and confirmation of a billing-free interface

Capacity: 20 points · Committed: 13

| Key | Type | Title | Points | Role | Depends on |
|---|---|---|---|---|---|
| US-020 | Story | Configure and run the app with a Gemini API key | 5 | devops-agent | US-001, US-002, US-007, US-019 |
| ↳ US-020-T1 | Task | Write setup notes | — | devops-agent | — |
| ↳ US-020-T2 | Task | Add startup key validation | — | backend-agent | — |
| ↳ US-020-T3 | Task | Verify key never reaches the client | — | security-agent | — |
| ↳ US-020-T4 | Task | Run clean-environment walkthrough | — | qa-agent | — |
| US-021 | Story | Run as a free internal tool with no billing | 1 | frontend-agent | — |
| ↳ US-021-T1 | Task | Audit UI for billing elements | — | frontend-agent | — |
| US-022 | Story | Correct chat message bubble alignment | 2 | frontend-agent | — |
| US-023 | Story | Apply blue/purple accent color tokens across the app | 3 | frontend-agent | — |
| US-024 | Story | Verify no visual regressions from the new accent color palette | 2 | qa-agent | — |

## Unscheduled

_Nothing unscheduled._
<!-- sdlc:auto:end sprints -->
