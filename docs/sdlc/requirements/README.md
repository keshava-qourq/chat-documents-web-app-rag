# Product Requirements

> Maintained by QuorQ AI SDLC. Text between `sdlc:auto` markers is regenerated; anything outside them is yours and is kept.

<!-- sdlc:auto:start narrative -->
## Summary

### REQ-META · draft · source: requirements:meta

Overview of project scope and requirements versioning for the 'chat documents' RAG web app.

Delivery scope: lightweight. Requirements version: 3. Project builds a 'chat with your documents' RAG chatbot using Google Gemini, with no sign-up, login or user accounts -- everyone shares one workspace where all documents and conversations are visible to all visitors, and conversation history is retained server-side.

**Related:** EPIC-001, EPIC-002, EPIC-003, EPIC-004, EPIC-005

- ⚠ No approval date or approver name is given for requirements version 3.

### REQ-TECHSTACK · approved · source: requirements:techstack

Product owner approved an exact technology stack: FastAPI backend, AWS cloud, PostgreSQL 16 with pgvector, React 19 frontend.

Backend: FastAPI 0.115 -- handles server-side PDF/DOCX text extraction, chunking, Gemini calls for embeddings/answers, streaming, and per-IP rate limiting at 5-25 user scale. Cloud: AWS -- managed Postgres with pgvector plus S3 for original files in one account/bill; runs on smallest instances at this scale. Database: PostgreSQL 16 -- single database for file records/status, chunks, pgvector embeddings, and shared conversation threads; deletion removes chunks transactionally. Frontend: React 19. Stated as approved and to be designed against exactly, with no substitution.

**Related:** EPIC-001, EPIC-002, EPIC-003, EPIC-004, EPIC-005

### REQ-SERVICES · approved · source: requirements:services

Approved runtime services: Google Gemini (SaaS), pgvector inside Postgres, and MinIO for file storage.

AI provider: Google Gemini (SaaS, env GEMINI_API_KEY) for both answer generation and embeddings on a single server-side key. Vector store: pgvector inside the same PostgreSQL database as files/chats -- no separate service. File storage: MinIO (S3-compatible), container bitnamilegacy/minio:2024.10.13, for original uploaded files. Required API key: GEMINI_API_KEY. Explicitly removed from the stack: a queue (Redis) and a cache (Redis).

**Related:** US-002, US-007, US-020, EPIC-001, EPIC-003

### REQ-OOS · approved · source: requirements:out_of_scope

Explicit out-of-scope list for this release.

Not to be designed or built: user accounts/sign-up/login/per-user permissions/private documents; Google Drive or cloud storage sync; web page (URL) ingestion; spreadsheet/slide (XLSX, PPTX) support; OCR of scanned/image-only PDFs; general-knowledge answers outside uploaded documents; per-conversation document selection/filtering; native mobile/desktop apps; voice input/output; image/video generation; email/SMS/push notifications; keyword search over documents; conversation export/sharing; automatic per-document summaries; a queue service; a cache service.

**Related:** EPIC-001, EPIC-002, EPIC-003, EPIC-004, EPIC-005

### EPIC-001 · draft · source: requirements:EPIC-001

Document upload and background indexing: browser upload, server-side extraction/chunking/embedding via Gemini, with visible progress.

Team members add documents to the shared library via browser upload; each file is stored, text-extracted, split into overlapping chunks, embedded with Gemini, and saved for retrieval by a background process while the UI shows progress. Assumptions: only PDF, DOCX, TXT/Markdown accepted (no spreadsheets/slides/URL/Drive sync); uploads capped at ~25MB/file, multiple files per upload allowed; no OCR so scanned/image-only PDFs fail or are unsearchable; embeddings generated via Gemini on a single operator-supplied GEMINI_API_KEY; background indexing runs without a dedicated queue service, sized for ~5-25 users and hundreds of documents.

**Related:** US-001, US-002, US-003

- ⚠ Exact chunk size/overlap configuration and the number of embedding retries before marking a document 'failed' are not specified.

### EPIC-002 · draft · source: requirements:EPIC-002

Shared document library screen for browsing and deleting uploaded files, with a cap on total stored documents.

A single shared documents screen lists every uploaded file so anyone can see what the assistant can answer from and remove outdated/incorrect files. Assumptions: access is fully open -- any visitor can delete any document, with no undo, no recovery, and no deletion record; this was surfaced to the human and left unchanged. No retention/expiry policy exists; documents persist until deleted. A cap on total stored documents applies to protect storage and Gemini quota.

**Related:** US-004, US-005, US-006

- ⚠ Whether deletion should be restricted or made recoverable (soft-delete) was raised but not decided -- carried as an explicit open assumption (see US-005).

### EPIC-003 · draft · source: requirements:EPIC-003

Grounded chat screen answering strictly from uploaded documents, with citations, streaming, and follow-up context.

Questions are answered using Gemini for generation over chunks retrieved from the shared library. Assumptions: every question searches the entire shared library, with no per-conversation document restriction; the assistant never answers from general knowledge and states plainly when documents lack the answer; Gemini generation runs on the operator's single server-side GEMINI_API_KEY.

**Related:** US-007, US-008, US-009, US-010, US-011, US-012, US-022

- ⚠ Gemini error/timeout handling for chat requests does not specify retry counts or timeout thresholds (see US-007).

### EPIC-004 · draft · source: requirements:EPIC-004

Shared conversation history: a sidebar of all threads, server-stored, viewable and editable by anyone.

All conversations live server-side as one shared list of threads in a sidebar so the team can revisit and continue each other's questions. Assumptions: shared unauthenticated history means no question is private -- any visitor can read, continue, rename or delete anything anyone asked; threads are auto-titled from the first question and renameable by anyone; thread deletion is permanent with no undo or deletion record; conversations persist until deleted, with no retention/expiry policy.

**Related:** US-013, US-014, US-015, US-016

### EPIC-005 · draft · source: requirements:EPIC-005

App shell and operational guardrails making an unauthenticated, internet-reachable tool viable for a small trusted team.

No login or shared password gate -- anyone with the URL can read and change everything. Per-IP rate limiting on chat and upload endpoints, plus the document cap, is the only protection for the operator's Gemini quota. Gemini powers both answers and embeddings on a single server-side GEMINI_API_KEY; no payments, plans or billing exist anywhere in the product. English-only interface, light/neutral styling, responsive browser-only app (no native apps). No fixed deadline was given; 'usable soon' was assumed.

**Related:** US-017, US-018, US-019, US-020, US-021, US-023, US-024

- ⚠ No fixed delivery deadline was confirmed -- 'usable soon' is an assumption, not a committed date.

### US-001 · draft · source: requirements:US-001

[critical] Team members upload one or more PDF, DOCX or TXT/Markdown files from the browser into the shared library.

A team member uploads one or more supported files so their content becomes available to ask questions about. AC-001: selecting/dragging several supported files at once and confirming upload accepts and stores each, immediately showing status 'processing' in the shared library. AC-002: a file of unsupported type (e.g. XLSX, PPTX) is rejected before upload with a message naming the supported formats, and no library entry is created. AC-003: a file over the ~25MB limit is rejected with a size-limit message, while other valid files in the same selection still upload. AC-004: if one file in a multi-file upload fails, the remaining files continue uploading and the failure is reported individually, not as a batch abort.

**Related:** EPIC-001, US-002, US-003

### US-002 · draft · source: requirements:US-002

[critical] Uploaded text is extracted, chunked with overlap, and embedded via Gemini in the background without blocking the user.

AC-005: once a file uploads successfully, background processing extracts text, splits it into overlapping chunks, requests Gemini embeddings, and stores chunks, embeddings and source location (file name + page/section). AC-006: processing continues server-side even if the user leaves the documents screen or closes the browser. AC-007: on completion, status becomes 'ready' and chunks become retrievable by chat queries. AC-008: if Gemini errors or is unavailable and retries are exhausted, the document is marked 'failed' with a short reason, and no partial/orphaned chunks remain in the index.

**Related:** EPIC-001, US-001, US-003

- ⚠ Specific chunk size/overlap values and the number of embedding retries before failure are not specified in this input.

### US-003 · draft · source: requirements:US-003

[high] Team members see whether each upload is processing, ready, or failed, with progress updates.

AC-009: while indexing, the documents screen shows a 'processing' state with a progress indication that updates without manual page reload. AC-010: a failed document shows status 'failed' with a human-readable reason (e.g. 'no extractable text found', 'embedding service error'). AC-011: a scanned/image-only PDF that yields no usable text (no OCR supported) is marked 'failed' with a reason noting no text could be extracted and that scanned documents are unsupported, and contributes nothing to chat answers.

**Related:** EPIC-001, US-001, US-002

### US-004 · draft · source: requirements:US-004

[high] Team members browse the shared document library showing name, size, upload time and status.

AC-012: opening the documents screen shows all documents in the single shared workspace, each with file name, size, upload date/time and status (processing/ready/failed). AC-013: when no documents exist, an empty state explains that uploading PDF/DOCX/TXT/Markdown files is how the assistant learns to answer. AC-014: if another visitor uploads or deletes a document while the screen is open, refreshing shows the same shared list with no per-user filtering.

**Related:** EPIC-002, US-005, US-006

### US-005 · draft · source: requirements:US-005

[high] Any visitor can permanently delete a document, removing it and its chunks from the search index.

AC-015: deleting a document (after confirming an irreversible-deletion warning) removes the document, its stored original file, and all its chunks/embeddings, and it disappears from the library. AC-016: after deletion, no chunk or citation from that document appears in future answers. AC-017: because the app has no accounts, any visitor can delete any document with no restriction, no undo, and no record of who did it -- this is the agreed open-access behaviour. AC-018: deleting a document still in 'processing' stops/discards its in-flight indexing and leaves no chunks in the index.

**Related:** EPIC-002, US-004, US-006

- ⚠ AC-017 is explicitly flagged in the source as an open assumption pending a decision on restricted or recoverable (soft) deletion.

### US-006 · draft · source: requirements:US-006

[medium] The library enforces a configurable cap on total stored documents to protect storage and Gemini quota.

AC-019: once the configured maximum document count is reached, new uploads are rejected with a message explaining the library is full and an existing document must be deleted first. AC-020: deleting a document when at the cap immediately re-enables uploading, with no restart needed. AC-021: the cap is set via configuration and read at app start; a documented default applies if none is set.

**Related:** EPIC-002, US-004, US-005

- ⚠ The numeric cap value and its documented default are not specified in this input.

### US-007 · draft · source: requirements:US-007

[critical] Chat answers are generated only from retrieved document chunks across the whole shared library.

AC-022: when 'ready' documents exist, submitting a question retrieves the most relevant chunks from across the whole shared library and generates an answer using only those chunks. AC-023: there is no control to limit search to particular documents -- every question searches the entire library by design. AC-024: if no documents exist or none are 'ready', the assistant replies that there are no indexed documents to answer from and points to the documents screen, rather than answering from general knowledge. AC-025: if the Gemini API errors or times out, the chat shows a clear error message and the question remains available to retry without corrupting the thread.

**Related:** EPIC-003, US-008, US-009

- ⚠ Retry count and timeout threshold for Gemini chat errors are not specified.

### US-008 · draft · source: requirements:US-008

[critical] The assistant plainly states when the uploaded documents do not contain the answer, instead of guessing.

AC-026: if retrieval finds no sufficiently relevant chunks, the assistant states the answer was not found in the uploaded documents, with no guessed answer and no citations. AC-027: if retrieved chunks only partially cover the question, the assistant answers the covered part with citations and explicitly states what is not covered. AC-028: a general-knowledge question unrelated to any uploaded document is declined with the same 'not found in the documents' response rather than being answered from the model's own knowledge.

**Related:** EPIC-003, US-007, US-009

### US-009 · draft · source: requirements:US-009

[critical] Every answer shows source citations with file name and page/section.

AC-029: answers list the source documents used, each showing file name and page number or section identifier. AC-030: when an answer draws on several documents, each distinct source is listed separately and de-duplicated, with no uncited source shown. AC-031: when the assistant replies 'not found in the documents', no citations are shown.

**Related:** EPIC-003, US-007, US-010

### US-010 · draft · source: requirements:US-010

[high] Citations can be expanded to show the exact retrieved excerpt behind an answer.

AC-032: expanding a citation shows the exact retrieved chunk text along with its file name and page/section. AC-033: collapsing a citation hides the excerpt again while the answer remains unchanged. AC-034: if the source document behind a citation was since deleted, expanding it in an older thread shows that the source document is no longer in the library, rather than an error.

**Related:** EPIC-003, US-009

### US-011 · draft · source: requirements:US-011

[high] Answers stream in progressively, token by token, rather than appearing all at once.

AC-035: once Gemini begins generating, text appears progressively in the chat rather than only on completion. AC-036: when streaming finishes, citations are displayed and the completed message with citations is persisted to the thread. AC-037: if the connection drops mid-stream, reopening the thread shows either the completed stored answer or a clear indication it did not complete, with the ability to ask again.

**Related:** EPIC-003, US-007

### US-012 · draft · source: requirements:US-012

[high] Follow-up questions use the thread's earlier turns as context for interpretation and retrieval.

AC-038: a follow-up using a pronoun or implicit reference to an earlier turn is interpreted using the thread's prior turns, resolving the reference correctly. AC-039: in a brand-new thread, no context from any other thread is applied. AC-040: in a long thread, requests stay within the model's context limit by including the most recent relevant turns, and the answer is still produced successfully.

**Related:** EPIC-003, US-007, US-013

- ⚠ The exact strategy for selecting 'most recent relevant turns' when truncating long-thread context is not fully specified.

### US-022 · draft · source: requirements:US-022

[low] Chat message bubbles for questions and answers must be correctly and consistently aligned.

AC-071: user messages are consistently aligned to one side and assistant messages to the other, with no overlap or misaligned edges. AC-072: while an answer streams, the bubble keeps correct alignment and resizes without shifting position. AC-073: bubbles with citations or long wrapped content remain correctly aligned and sized without overflowing the chat column. AC-074: on narrow mobile browsers, bubbles remain aligned and readable without horizontal scrolling. AC-075: reopening a long existing thread displays every historical bubble, old and new, with the corrected alignment.

**Related:** EPIC-003, US-011

### US-013 · draft · source: requirements:US-013

[high] A sidebar lists every shared conversation thread, most recently active first.

AC-041: opening the chat screen shows the sidebar listing all threads in the shared workspace, most recently active first, each showing its title. AC-042: every visitor sees every other visitor's threads with no filtering or privacy -- the agreed open-access behaviour. AC-043: when no conversations exist, an empty sidebar state is shown and a new conversation can be started immediately.

**Related:** EPIC-004, US-014

### US-014 · draft · source: requirements:US-014

[high] Any visitor can start a new thread or open and continue any existing shared thread.

AC-044: choosing 'new conversation' opens an empty thread, persisted to the shared list once its first question is sent. AC-045: opening an existing thread loads its full Q&A history, including each answer's citations, in order. AC-046: sending a new question in someone else's thread appends it to that same shared thread, visible to everyone, using the thread's earlier turns as context. AC-047: reloading the browser or opening the app from another device still shows the thread and its messages, since history is stored server-side.

**Related:** EPIC-004, US-013, US-012

### US-015 · draft · source: requirements:US-015

[medium] A new thread is automatically titled from its first question.

AC-048: sending the first question in a new thread gives it a short title derived from that question, shown in the sidebar. AC-049: a very long first question produces a title truncated to a readable sidebar length without breaking layout. AC-050: once auto-titled, the title does not change automatically as further questions are asked.

**Related:** EPIC-004, US-014

### US-016 · draft · source: requirements:US-016

[medium] Any visitor can rename or permanently delete any thread.

AC-051: renaming any thread, including one started by someone else, stores the new title server-side and shows it to every visitor. AC-052: attempting to save an empty title is rejected and the previous title is kept. AC-053: deleting a thread (after confirming an irreversible-deletion warning) removes the thread and all its messages for everyone, with no undo and no record of who deleted it. AC-054: deleting the currently viewed thread returns the chat area to an empty/new conversation state rather than showing a broken thread.

**Related:** EPIC-004, US-013, US-015

- ⚠ AC-053's unrestricted, unlogged thread deletion is recorded as an open assumption of the open-access model, same as document deletion (US-005).

### US-017 · draft · source: requirements:US-017

[critical] The app requires no sign-up, login or password -- anyone with the link gets full shared access.

AC-055: opening the URL for the first time lands directly in the shared workspace with full access to chat, history and documents, no sign-up/login/shared-password prompt. AC-056: two different people on different machines see exactly the same documents and threads, with no per-person data separation. AC-057: any unknown visitor who finds the URL can also read, upload and delete everything -- the accepted risk of the agreed open-access model.

**Related:** EPIC-005, US-018

- ⚠ AC-057's fully open access to unknown internet visitors is recorded as an accepted-risk assumption rather than a resolved security control.

### US-018 · draft · source: requirements:US-018

[high] The app provides a responsive two-area layout (chat+sidebar and documents) usable on desktop and mobile.

AC-058: on desktop, the chat screen shows the thread sidebar alongside it, and switching to the documents screen preserves the open thread. AC-059: on narrow mobile browsers, the layout adapts so sidebar, chat and documents areas are each reachable and usable without horizontal scrolling. AC-060: all labels, statuses and messages are in English, rendered in the agreed neutral style, with no language switcher.

**Related:** EPIC-005, US-017

### US-019 · draft · source: requirements:US-019

[high] Server-side per-IP rate limits on chat and upload endpoints protect the operator's Gemini quota.

AC-061: when one IP exceeds the configured chat rate limit within the configured window, further chat requests from it are rejected with a 'too many requests, try again shortly' message and no Gemini call is made. AC-062: when one IP exceeds the configured upload rate limit, further uploads are rejected with a clear message and no file is stored or embedded. AC-063: once the limit window elapses, requests from that IP are accepted again automatically. AC-064: normal use by the expected 5-25 person team does not trigger the limits, and limit values are operator-configurable.

**Related:** EPIC-005, US-001, US-007

- ⚠ Specific rate-limit thresholds and window durations are not given, only that they must be configurable.

### US-020 · draft · source: requirements:US-020

[high] Setup notes document the GEMINI_API_KEY and all configuration needed to run and deploy the app.

AC-065: setup notes list every required configuration value -- GEMINI_API_KEY, the database/pgvector connection, object storage, document cap, and rate-limit settings -- and how to set each. AC-066: following the setup notes from a clean environment starts the app locally and allows uploading a document and getting a cited answer. AC-067: a missing or invalid GEMINI_API_KEY surfaces a clear configuration error naming the missing/rejected key rather than a generic failure. AC-068: the key is server-side only -- never exposed to the browser -- and all Gemini calls for answers and embeddings are made from the server.

**Related:** EPIC-005, REQ-SERVICES, REQ-TECHSTACK

### US-021 · draft · source: requirements:US-021

[low] The app has no payments, plans, subscriptions or billing anywhere -- it is a free internal tool.

AC-069: no screen shows pricing, plan, paywall, quota-purchase or payment elements. AC-070: Gemini usage incurred by chat and embedding calls is charged solely to the operator's own Gemini account; the app bills no one -- an agreed assumption.

**Related:** EPIC-005

### US-023 · draft · source: requirements:US-023

[low] Buttons, links and active/selected states adopt a new blue-to-purple accent color palette.

AC-076: primary action buttons (e.g. 'Upload', 'Send', 'New conversation') use the new blue (#4285F4)-to-purple (#9168C0) accent instead of the previous primary color, with no change to size, position or label. AC-077: hyperlinks/text links styled with the primary color resolve to the new accent token value. AC-078: active/selected elements (e.g. the open thread in the sidebar, the active nav tab) are highlighted with the new accent color. AC-079: in both light and dark mode, backgrounds, spacing, typography and layout remain exactly as delivered -- only accent/primary color tokens change. AC-080: the change is made only by updating CSS custom property / Tailwind token values, with no new components, classes or structural markup introduced.

**Related:** EPIC-005, US-024, US-018

### US-024 · draft · source: requirements:US-024

[low] Verify the new accent color palette introduces no visual regressions across all existing screens.

AC-081: on the documents screen, chat screen, thread sidebar, citations panel and mobile responsive layout, layout/spacing/component positions are unchanged from before the color update. AC-082: text and controls on the new accent background/foreground remain legible (adequate contrast) in both light and dark mode. AC-083: all interactive elements that previously used the primary color consistently show the new blue-to-purple accent across every delivered screen, with no element left on the old primary color.

**Related:** EPIC-005, US-023
<!-- sdlc:auto:end narrative -->

<!-- sdlc:auto:start summary -->
**Requirements version:** v3  
**Delivery scope:** lightweight  
**Approved:** 2026-10-25

**Capabilities in scope:** Browser upload of PDF, DOCX and TXT/Markdown files, Text extraction, overlapping chunking and Gemini embedding of each upload, Shared document library with name, size, upload time and indexing status, Background indexing with visible processing / ready / failed progress, Delete a document, removing its chunks from the search index, Chat screen answering strictly from the uploaded documents, Source citations showing file name and page/section on every answer, Expandable citation showing the retrieved excerpt behind an answer, "Not found in the documents" response instead of a guessed answer, Streamed answers that appear token by token, Follow-up questions that carry the thread's earlier turns, Shared sidebar list of conversation threads, Start, open and continue any conversation thread, Auto-titling of a thread from its first question, Rename or delete any conversation thread, Responsive two-area layout (chat and documents), Setup notes covering the Gemini API key and running the app, Google Gemini for both answers and embeddings, on your own GEMINI_API_KEY, Open to anyone with the link — no login and no shared password, Uploads capped at about 25 MB per file, several files at a time, Every chat searches the whole library — no per-chat document picking, No OCR, so scanned image-only PDFs show as failed or unsearchable, Documents and conversations persist until someone deletes them, Anyone can delete any document or thread, with no undo, English-only interface with light/neutral styling, No payments or billing — Gemini usage sits on your account

**Approved technology stack:**

| Layer | Choice | Rationale |
|---|---|---|
| backend | FastAPI | Everything hard in this product happens on the server: pulling text out of PDFs and DOCX files, splitting it into overlapping chunks, calling Gemini for embeddings and for answers, and streaming those answers back. Python has the most mature, best-tested libraries for document text extraction and chunking, which is exactly where a document-chat app succeeds or fails. FastAPI handles streaming responses and per-IP rate limiting on chat and upload comfortably at your 5–25 user scale. |
| cloud | AWS | You asked for a managed cloud host. AWS gives you managed Postgres with pgvector and S3 for the original uploaded files in one account, with one bill, which is what a small internal tool wants. At 5–25 users this runs on the smallest instances and costs little; the real spend stays on your Gemini key. |
| database | PostgreSQL | One database holds the lot: file records and their processing status, the text chunks, the embedding vectors via the pgvector extension, and the shared conversation threads. With hundreds of documents and a few thousand chunks, Postgres searches your library fast enough that nobody notices, and deleting a document genuinely removes its chunks from the index in the same transaction — no second system to fall out of sync. |
| frontend | React | — |
<!-- sdlc:auto:end summary -->

<!-- sdlc:auto:start epics -->
## EPIC-001: Document upload and background indexing

Team members add work documents to the shared library by uploading them directly in the browser. Each upload is stored, its text extracted, split into overlapping chunks, embedded with Google Gemini and saved for retrieval by a background process, while the UI shows progress.

Assumptions surfaced from the confirmed understanding:
- Accepted formats are PDF, DOCX and TXT/Markdown only. Spreadsheets, slides, URL ingestion and Google Drive sync are out of scope.
- Uploads are capped at approximately 25 MB per file; several files may be selected in one upload.
- There is no OCR, so scanned/image-only PDFs will yield no text and will end up marked failed or effectively unsearchable.
- Embeddings are generated by Gemini using a single server-side GEMINI_API_KEY supplied by the operator; Gemini costs sit on that account.
- Background indexing runs without a dedicated queue service (Redis was removed from the stack); it is sized for ~5-25 users and hundreds of documents.

### US-001: Upload documents from the browser

**Priority:** critical

> As a team member, I want to upload one or more PDF, DOCX or TXT/Markdown files from my browser into the shared library, so that their content becomes available to ask questions about.

| ID | Given | When | Then |
|---|---|---|---|
| AC-001 | I am on the documents screen | I select or drag several supported files (PDF, DOCX, TXT or Markdown) at once and confirm the upload | each file is accepted, stored, and appears immediately in the shared document library with status 'processing' |
| AC-002 | I am on the documents screen | I choose a file whose type is not PDF, DOCX, TXT or Markdown (for example XLSX or PPTX) | the file is rejected before upload with a message naming the supported formats, and no entry is created in the library |
| AC-003 | I am on the documents screen | I choose a file larger than the ~25 MB per-file limit | that file is rejected with a message stating the size limit, and any other valid files in the same selection still upload |
| AC-004 | an upload of several files is in progress | one file fails to upload | the remaining files continue and the failing file is reported individually rather than aborting the whole batch |

### US-002: Extract, chunk and embed uploaded text in the background

**Priority:** critical

> As a team member, I want the app to extract text from my upload, split it into overlapping chunks and embed them with Gemini without me waiting on the screen, so that the document becomes searchable and I can keep working while it processes.

| ID | Given | When | Then |
|---|---|---|---|
| AC-005 | a supported file has been uploaded successfully | background processing starts | the system extracts the document text, splits it into chunks with a configured overlap, requests embeddings from Gemini and stores the chunks, their embeddings and their source location (file name plus page or section) |
| AC-006 | a document is being processed | I leave the documents screen or close the browser | processing continues server-side and the document reaches its final status without my browser being open |
| AC-007 | a document has finished embedding | processing completes | its status changes to 'ready' and its chunks are retrievable by chat queries |
| AC-008 | Gemini returns an error or is unavailable during embedding | the system has exhausted its retries for that document | the document is marked 'failed' with a short reason shown in the library, and no partial or orphaned chunks remain in the search index |

### US-003: See processing progress and failures

**Priority:** high

> As a team member, I want to see whether each upload is processing, ready or failed, with progress while it works, so that I know when I can ask questions about it and when something went wrong.

| ID | Given | When | Then |
|---|---|---|---|
| AC-009 | a document is being indexed | I view the documents screen | the document shows a 'processing' state with a visible progress indication that updates as indexing proceeds, without me reloading the page manually |
| AC-010 | a document failed to index | I view the documents screen | it shows status 'failed' together with a human-readable reason (for example 'no extractable text found' or 'embedding service error') |
| AC-011 | I upload a scanned or image-only PDF, which this release cannot OCR | text extraction yields no usable text | the document is marked 'failed' with a reason indicating no text could be extracted and that scanned documents are not supported, and it contributes nothing to chat answers |

## EPIC-002: Shared document library

A single shared documents screen listing every uploaded file so anyone on the team can see what the assistant can answer from, and remove files that are wrong or out of date.

Assumptions surfaced from the confirmed understanding:
- Access is fully open: any visitor with the link can delete any document. There is no undo, no recovery and no record of who deleted it. The human was asked whether deletion should be restricted or soft-delete and has not changed this.
- There is no retention or expiry policy; documents persist until someone deletes them.
- A cap on the total number of stored documents applies, to protect storage and Gemini quota.

### US-004: Browse the shared document library

**Priority:** high

> As a team member, I want to see every uploaded document with its name, size, upload time and indexing status, so that I know what the assistant can draw on.

| ID | Given | When | Then |
|---|---|---|---|
| AC-012 | documents have been uploaded by anyone on the team | I open the documents screen | I see a list of all documents in the single shared workspace, each showing file name, file size, upload date/time and status (processing / ready / failed) |
| AC-013 | no documents have been uploaded yet | I open the documents screen | I see an empty state explaining that uploading PDF, DOCX or TXT/Markdown files is how the assistant learns to answer |
| AC-014 | another visitor uploads or deletes a document while I have the documents screen open | I refresh or the list next updates | I see the same shared list they see, with no per-user filtering |

### US-005: Delete a document and remove it from the index

**Priority:** high

> As a team member, I want to delete a document so it stops being used in answers, so that outdated or incorrect material is not cited by the assistant.

| ID | Given | When | Then |
|---|---|---|---|
| AC-015 | a document in the library | I choose to delete it and confirm the warning that deletion is permanent and cannot be undone | the document, its stored original file and all of its chunks and embeddings are removed, and it disappears from the library |
| AC-016 | a document has just been deleted | someone asks a question that would previously have been answered from that document | no chunk or citation from the deleted document appears in the answer |
| AC-017 | the app is open to anyone with the link and has no accounts | any visitor deletes a document | the deletion succeeds with no restriction, no undo and no record of who performed it — this is the agreed open-access behaviour and is flagged as an open assumption pending a decision on restricted or recoverable deletion |
| AC-018 | a document is still in 'processing' state | I delete it | its in-flight indexing is stopped or discarded and no chunks for it are left in the search index |

### US-006: Enforce a cap on total stored documents

**Priority:** medium

> As a operator of the app, I want the library to refuse new uploads once a configured total document cap is reached, so that an anonymous visitor cannot exhaust storage or the Gemini embedding quota.

| ID | Given | When | Then |
|---|---|---|---|
| AC-019 | the library already holds the configured maximum number of documents | anyone attempts a new upload | the upload is rejected with a message explaining the library is full and that an existing document must be deleted first |
| AC-020 | the library is at its cap | someone deletes a document | uploading becomes possible again without any restart or manual intervention |
| AC-021 | the operator has set the cap via configuration | the app starts | the configured cap value is used, and a documented default applies if none is set |

## EPIC-003: Grounded chat with citations

The chat screen where questions are answered strictly from the uploaded documents, using Gemini for generation over chunks retrieved from the shared library.

Assumptions surfaced from the confirmed understanding:
- Every question searches the entire shared library. There is no way to restrict a conversation to selected documents.
- The assistant never answers from general knowledge; when the documents do not contain the answer it says so.
- Gemini is used for generation on the operator's single server-side GEMINI_API_KEY.

### US-007: Ask a question answered only from the documents

**Priority:** critical

> As a team member, I want to ask a question in the chat and get an answer built only from the uploaded documents, so that I can trust the answer reflects our own material rather than the model's general knowledge.

| ID | Given | When | Then |
|---|---|---|---|
| AC-022 | documents with status 'ready' exist in the library | I submit a question in the chat | the system retrieves the most relevant chunks from across the whole shared library and generates an answer using only those chunks as its source material |
| AC-023 | I am composing a question | I look for a way to limit the search to particular documents | no such control exists — every question searches the entire library, which is the agreed behaviour for this release |
| AC-024 | no documents have been uploaded or none are 'ready' | I submit a question | the assistant replies that there are no indexed documents to answer from and points me to the documents screen, rather than answering from general knowledge |
| AC-025 | the Gemini API returns an error or times out | I submit a question | the chat shows a clear error message and my question remains available to retry, without the thread being corrupted |

### US-008: Say when the answer is not in the documents

**Priority:** critical

> As a team member, I want the assistant to tell me plainly when the documents do not contain the answer, so that I am not misled by an invented answer.

| ID | Given | When | Then |
|---|---|---|---|
| AC-026 | retrieval returns no sufficiently relevant chunks for my question | the assistant responds | it states that the answer was not found in the uploaded documents and offers no guessed answer and no citations |
| AC-027 | the retrieved chunks only partially cover my question | the assistant responds | it answers the covered part with citations and explicitly states which part is not covered by the documents |
| AC-028 | I ask a general-knowledge question unrelated to any uploaded document (for example a world fact) | the assistant responds | it declines with the 'not found in the documents' response rather than answering from the model's own knowledge |

### US-009: See source citations on every answer

**Priority:** critical

> As a team member, I want each answer to show which file and page/section it came from, so that I can verify the answer against the original document.

| ID | Given | When | Then |
|---|---|---|---|
| AC-029 | the assistant has produced an answer from retrieved chunks | the answer is displayed | it lists the source documents used, each showing the file name and the page number or section identifier the content came from |
| AC-030 | an answer draws on several documents | the answer is displayed | each distinct source is listed separately and de-duplicated, with no source cited that was not actually retrieved for that answer |
| AC-031 | the assistant replied that the answer is not in the documents | the answer is displayed | no citations are shown |

### US-010: Expand a citation to read the retrieved excerpt

**Priority:** high

> As a team member, I want to expand a citation and read the exact excerpt the answer was based on, so that I can judge for myself whether the answer is well supported.

| ID | Given | When | Then |
|---|---|---|---|
| AC-032 | an answer with one or more citations | I expand a citation | the exact retrieved chunk text is shown together with its file name and page/section |
| AC-033 | a citation is expanded | I collapse it | the excerpt hides again and the answer remains readable and unchanged |
| AC-034 | the document behind a citation has since been deleted | I open an older thread and expand that citation | the excerpt area shows that the source document is no longer in the library rather than failing with an error |

### US-011: Watch answers stream in token by token

**Priority:** high

> As a team member, I want the answer to appear progressively as it is generated, so that I get feedback immediately instead of staring at a spinner.

| ID | Given | When | Then |
|---|---|---|---|
| AC-035 | I have submitted a question | Gemini begins generating the answer | text appears progressively in the chat as it is produced, rather than only when the full answer is complete |
| AC-036 | an answer is still streaming | generation finishes | the citations are displayed and the completed message with its citations is persisted to the thread |
| AC-037 | the connection drops part-way through streaming | I reopen the thread | I see either the completed stored answer or a clear indication that the answer did not complete, with the ability to ask again |

### US-012: Ask follow-up questions in context

**Priority:** high

> As a team member, I want my follow-up questions to take the earlier turns of the thread into account, so that I can say "and what about last year?" without repeating the whole question.

| ID | Given | When | Then |
|---|---|---|---|
| AC-038 | a thread with earlier question-and-answer turns | I ask a follow-up that uses a pronoun or an implicit reference to an earlier turn | the system includes the thread's prior turns when interpreting the question and retrieving chunks, and the answer resolves the reference correctly |
| AC-039 | I start a brand new thread | I ask a question that would only make sense as a follow-up | no context from any other thread is applied and the assistant answers only on the basis of the new thread's content |
| AC-040 | a thread has grown long | I ask another follow-up | the request stays within the model's context limit by including the most recent relevant turns, and the answer is still produced successfully |

### US-022: Correct chat message bubble alignment

**Priority:** low

> As a team member, I want the chat message bubbles for my questions and the assistant's answers to be correctly aligned, so that the conversation is easy to read and visually consistent across devices.

| ID | Given | When | Then |
|---|---|---|---|
| AC-071 | an open thread with my questions and the assistant's answers | the chat area renders | my messages are consistently aligned to one side and the assistant's messages to the other, with no overlap or misaligned bubble edges |
| AC-072 | an answer is streaming in token by token | new tokens are appended | the bubble keeps its correct alignment and grows/resizes without shifting out of position |
| AC-073 | a message bubble contains citations or a long answer | the content wraps to multiple lines | the bubble remains correctly aligned and sized to its content without overflowing the chat column |
| AC-074 | the chat screen is viewed on a narrow mobile browser | messages are displayed | message bubbles remain correctly aligned and fully readable without horizontal scrolling |
| AC-075 | an existing long thread is reopened | its full history loads | every historical message bubble, old and new, displays with the corrected alignment |

## EPIC-004: Shared conversation history

All conversations live on the server as one shared list of threads in a sidebar, so the team can revisit and continue each other's questions.

Assumptions surfaced from the confirmed understanding:
- Shared, unauthenticated history means nobody's questions are private; any visitor can read, continue, rename or delete anything anyone asked.
- Threads are auto-titled from the first question and can be renamed by anyone.
- Deleting a thread is permanent, with no undo and no record of who did it.
- Conversations persist until someone deletes them; there is no retention or expiry policy.

### US-013: See the shared list of conversation threads

**Priority:** high

> As a team member, I want a sidebar listing all conversation threads the team has had, so that I can find and reuse earlier answers instead of asking again.

| ID | Given | When | Then |
|---|---|---|---|
| AC-041 | threads have been created by anyone using the app | I open the chat screen | the sidebar lists all threads in the shared workspace, most recently active first, each showing its title |
| AC-042 | the app has no accounts and history is shared | I view the sidebar | I see every other visitor's threads with no filtering and no privacy — this is the agreed open-access behaviour and is recorded as an open assumption |
| AC-043 | no conversations exist yet | I open the chat screen | I see an empty sidebar state and can start a new conversation straight away |

### US-014: Start, open and continue any thread

**Priority:** high

> As a team member, I want to start a new conversation or open and continue any existing one, so that I can pick up a line of questioning that someone else began.

| ID | Given | When | Then |
|---|---|---|---|
| AC-044 | I am on the chat screen | I choose 'new conversation' | an empty thread is opened, and it is persisted in the shared list once I send its first question |
| AC-045 | an existing thread in the sidebar | I open it | its full question-and-answer history, including each answer's citations, is loaded and displayed in order |
| AC-046 | I have opened a thread started by someone else | I send a new question in it | the question and its answer are appended to that same shared thread, visible to everyone, and the thread's earlier turns are used as context |
| AC-047 | a question and answer have been completed in a thread | I reload the browser or open the app from another device | the thread and its messages are still present, because history is stored server-side |

### US-015: Auto-title a thread from its first question

**Priority:** medium

> As a team member, I want each thread to be named automatically from its first question, so that I can recognise conversations in the sidebar without naming them myself.

| ID | Given | When | Then |
|---|---|---|---|
| AC-048 | a new thread with no messages | I send its first question | the thread is given a short title derived from that question and the title appears in the sidebar |
| AC-049 | a first question that is very long | the title is generated | the title is truncated to a readable length in the sidebar without breaking the layout |
| AC-050 | a thread that has already been auto-titled | further questions are asked in it | the title does not change automatically |

### US-016: Rename or delete any thread

**Priority:** medium

> As a team member, I want to rename a thread to something clearer, or delete it when it is no longer useful, so that the shared sidebar stays tidy and understandable.

| ID | Given | When | Then |
|---|---|---|---|
| AC-051 | any thread in the sidebar, including one started by someone else | I rename it and save | the new title is stored server-side and shown to every visitor |
| AC-052 | a rename with an empty title | I try to save it | the change is rejected and the previous title is kept |
| AC-053 | any thread in the sidebar | I choose to delete it and confirm the warning that deletion is permanent | the thread and all of its messages are removed for everyone, with no undo and no record of who deleted it — the agreed open-access behaviour, recorded as an open assumption |
| AC-054 | I delete the thread I am currently viewing | the deletion completes | the chat area returns to an empty/new conversation state rather than showing a broken thread |

## EPIC-005: Open access, abuse protection and operation

The app shell and the operational guardrails that make an unauthenticated, internet-reachable tool safe enough for a small trusted team.

Assumptions surfaced from the confirmed understanding:
- Completely open: no login and no shared password gate. Anyone with the URL can read and change everything.
- Per-IP rate limiting on the chat and upload endpoints, plus the document cap, is the only protection for the operator's Gemini quota.
- Gemini powers both answers and embeddings on a single server-side GEMINI_API_KEY; there are no payments, plans or billing of any kind and Gemini costs sit on the operator's account.
- English-only interface with light/neutral styling; responsive browser app only (no native apps).
- No fixed deadline was given; 'usable soon' was assumed.

### US-017: Use the app with no login or password

**Priority:** critical

> As a team member with the link, I want to use the app immediately without signing up or entering a password, so that there is no friction for a small trusted internal team.

| ID | Given | When | Then |
|---|---|---|---|
| AC-055 | I have never used the app before | I open the URL | I land directly in the shared workspace with full access to chat, history and documents, with no sign-up, login or shared-password prompt |
| AC-056 | two different people open the URL from different machines | each uses the app | both see exactly the same documents and the same conversation threads, with no per-person separation of data |
| AC-057 | the app is reachable by anyone who finds the URL | an unknown visitor opens it | they too can read, upload and delete everything — the accepted risk of the agreed open-access model, recorded as an open assumption |

### US-018: Navigate a responsive two-area layout

**Priority:** high

> As a team member, I want a chat area with a thread sidebar and a documents area, usable on a laptop or a phone browser, so that I can ask questions and manage files from wherever I am.

| ID | Given | When | Then |
|---|---|---|---|
| AC-058 | I am using the app on a desktop browser | I open it | I see the chat screen with the thread sidebar alongside it and can switch to the documents screen without losing my place in the open thread |
| AC-059 | I am using the app on a narrow mobile browser | I open it | the layout adapts so the sidebar, chat and documents areas are each reachable and usable without horizontal scrolling |
| AC-060 | the interface is English-only with light/neutral styling in this release | I use any screen | all labels, statuses and messages are in English and rendered in the agreed neutral style, with no language switcher |

### US-019: Rate limit chat and upload per IP

**Priority:** high

> As a operator of the app, I want server-side per-IP rate limits on the chat and upload endpoints, so that a stranger who finds the URL cannot burn through my Gemini quota.

| ID | Given | When | Then |
|---|---|---|---|
| AC-061 | a configured per-IP limit on chat requests | one IP exceeds that limit within the configured window | further chat requests from that IP are rejected with a clear 'too many requests, try again shortly' message and no Gemini call is made |
| AC-062 | a configured per-IP limit on uploads | one IP exceeds that limit within the configured window | further uploads from that IP are rejected with a clear message and no file is stored or embedded |
| AC-063 | an IP has been rate limited | the limit window elapses | requests from that IP are accepted again without any manual intervention |
| AC-064 | normal use by the expected 5-25 person team | they chat and upload at typical rates | the limits are not triggered, and the limit values are configurable by the operator |

### US-020: Configure and run the app with a Gemini API key

**Priority:** high

> As a operator of the app, I want setup notes covering the GEMINI_API_KEY and how to run and deploy the app, so that I can get the tool running for my team without guesswork.

| ID | Given | When | Then |
|---|---|---|---|
| AC-065 | the repository as delivered | I read the setup notes | they list every required configuration value — including GEMINI_API_KEY, the database/pgvector connection, object storage, the document cap and the rate limit settings — and how to set each |
| AC-066 | I follow the setup notes from a clean environment | I run the documented steps | the app starts locally and I can upload a document and get a cited answer |
| AC-067 | GEMINI_API_KEY is missing or invalid | the app starts or the first Gemini call is attempted | a clear configuration error is surfaced naming the missing or rejected key, rather than a generic failure |
| AC-068 | the key is server-side only | I inspect anything delivered to the browser | the GEMINI_API_KEY is never exposed to the client, and all Gemini calls for answers and embeddings are made from the server |

### US-021: Run as a free internal tool with no billing

**Priority:** low

> As a operator of the app, I want no payments, plans, subscriptions or usage billing anywhere in the product, so that the tool stays a simple free internal utility paid for only through my own Gemini account.

| ID | Given | When | Then |
|---|---|---|---|
| AC-069 | any screen of the app | a team member uses it | there is no pricing, plan, paywall, quota-purchase or payment element anywhere in the interface |
| AC-070 | Gemini usage is incurred by chat and embedding calls | that usage accumulates | it is charged solely to the operator's own Gemini account and the app bills no one — recorded as the agreed assumption that costs sit on the operator |

### US-023: Apply blue/purple accent color tokens across the app

**Priority:** low

> As a team member, I want the app's buttons, links and active/selected states to use the new blue-to-purple accent palette, so that the interface reflects the updated brand color theme without any change to how I use the app.

| ID | Given | When | Then |
|---|---|---|---|
| AC-076 | a primary action button (for example 'Upload', 'Send', 'New conversation') | the page renders | the button uses the new blue (#4285F4) to purple (#9168C0) accent color instead of the previous primary color, with no change to its size, position or label |
| AC-077 | a hyperlink or text link styled with the primary color | it is rendered | it resolves to the new accent color token value |
| AC-078 | an active or selected element such as the currently open thread in the sidebar or the active navigation tab | it is highlighted | the highlight uses the new accent color instead of the previous one |
| AC-079 | the app in either light or dark mode | either theme is active | backgrounds, spacing, typography and component layout remain exactly as delivered, and only the accent/primary color tokens change |
| AC-080 | the existing CSS custom properties / Tailwind color token definitions | the new palette is applied | the change is made only by updating token values, with no new components, classes, or structural markup introduced |

### US-024: Verify no visual regressions from the new accent color palette

**Priority:** low

> As a operator of the app, I want the updated blue/purple accent colors checked across all existing screens, so that the restyle introduces no layout shifts, broken contrast, or behavioural changes.

| ID | Given | When | Then |
|---|---|---|---|
| AC-081 | the documents screen, chat screen, thread sidebar, citations panel and mobile responsive layout | each is visually inspected after the token update | layout, spacing and component positions are unchanged from before the color update |
| AC-082 | text and controls rendered on the new accent background or foreground colors | checked for readability | text and icon contrast against the new accent color remains legible in both light and dark mode |
| AC-083 | all interactive elements that previously used the primary color (buttons, links, active states) | exercised across every delivered screen | they consistently show the new blue-to-purple accent and no element is left showing the old primary color |
<!-- sdlc:auto:end epics -->
