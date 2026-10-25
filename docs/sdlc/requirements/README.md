# Product Requirements

> Maintained by QuorQ AI SDLC. Text between `sdlc:auto` markers is regenerated; anything outside them is yours and is kept.

<!-- sdlc:auto:start narrative -->
## Summary

### REQ-STACK · approved · source: requirements:stack

Product owner approved an exact technology stack for this project: FastAPI 0.115 backend, AWS cloud, PostgreSQL 16 (with pgvector) database, React 19 frontend.

Stated rationale: server-side Python/FastAPI handles PDF/DOCX extraction, chunking, Gemini calls, streaming, and per-IP rate limiting at 5-25 user scale. AWS gives managed Postgres+pgvector and S3-compatible storage in one account/bill, sized to the smallest instances at this scale. PostgreSQL 16 with pgvector holds file records, processing status, chunks, embeddings and shared conversation threads in one transactional store so document deletion removes chunks atomically. React 19 is the approved frontend framework. Instruction is to design against exactly these choices, not substitute.

### REQ-SERVICES · approved · source: requirements:services

Product owner approved exactly three runtime services: Google Gemini (SaaS) for answers and embeddings, pgvector inside PostgreSQL as the vector store, and MinIO (container bitnamilegacy/minio:2024.10.13) as S3-compatible file storage.

Gemini is accessed via a single server-side GEMINI_API_KEY supplied by the operator and used for both embedding generation and answer generation; Gemini usage costs sit on the operator's account. pgvector keeps embeddings co-located with files/chats in the same Postgres instance so deleting a document removes it from search immediately, with no separate vector service to operate. MinIO stores the original uploaded files. The only required API key is GEMINI_API_KEY. A previously suggested Redis service (for queueing and for caching) was explicitly removed from the stack and is out of scope.

**Related:** US-001, US-002, US-007, US-019, US-020

- ⚠ No queue/cache service exists; the mechanism by which the documents screen receives live processing-status updates (polling interval vs. push) is not specified -- relevant to US-003.

### REQ-SCOPE · approved · source: requirements:scope

An explicit out-of-scope list excludes accounts/login/permissions, Drive sync, URL ingestion, XLSX/PPTX support, OCR, general-knowledge answers, per-conversation document filtering, native apps, voice, image/video generation, notifications, keyword search, conversation export/sharing, auto-summaries, and the Redis queue/cache.

Delivery scope is labeled 'lightweight'. Capabilities explicitly in scope: browser upload of PDF/DOCX/TXT/Markdown; text extraction, overlapping chunking and Gemini embedding; shared document library with status; background indexing with visible progress; document delete with index cleanup; grounded chat with citations (file + page/section); expandable citation excerpts; 'not found in the documents' fallback; token-by-token streaming; follow-up context; shared sidebar of threads; start/open/continue/rename/delete threads; auto-titling; responsive two-area layout; setup notes for GEMINI_API_KEY and running the app; no login; ~25MB/file cap, multi-file upload; whole-library search only; no OCR; persistent data until manually deleted; unrestricted delete with no undo; English-only, light/neutral UI; no billing.

### EPIC-001 · approved · source: requirements:EPIC-001

Covers browser upload of documents and server-side background indexing (extraction, chunking, Gemini embedding) with visible progress.

Team members upload PDF/DOCX/TXT/Markdown files directly in the browser; each file is stored, text-extracted, split into overlapping chunks, embedded via Gemini, and made retrievable, with the UI reflecting processing/ready/failed status. No OCR is performed, so scanned/image-only PDFs fail or are unsearchable. Indexing runs without a dedicated queue service, sized for ~5-25 users and hundreds of documents, on a single operator-supplied GEMINI_API_KEY.

**Related:** US-001, US-002, US-003

### EPIC-002 · approved · source: requirements:EPIC-002

A single shared documents screen lists every uploaded file so the whole team can see what the assistant can answer from, and remove files that are wrong or outdated.

Any visitor can delete any document with no undo, no recovery, and no record of who deleted it -- flagged as an open assumption pending a decision on whether to restrict or soft-delete. There is no retention/expiry policy; documents persist until manually deleted. A configurable cap on total stored documents protects storage and Gemini quota.

**Related:** US-004, US-005, US-006

- ⚠ Whether document deletion should remain fully unrestricted or move to soft-delete/restricted access is an explicitly unresolved decision (see US-005/AC-017).

### EPIC-003 · approved · source: requirements:EPIC-003

The chat screen answers questions strictly from the uploaded documents, using Gemini for generation over retrieved chunks, with citations and streaming.

Every question searches the entire shared library -- there is no per-conversation document selection. The assistant never answers from general knowledge; when documents don't contain the answer it says so explicitly rather than guessing. Generation uses the operator's single server-side GEMINI_API_KEY.

**Related:** US-007, US-008, US-009, US-010, US-011, US-012, US-022

### EPIC-004 · approved · source: requirements:EPIC-004

All conversations live server-side as one shared list of threads in a sidebar so the team can revisit and continue each other's questions.

Shared, unauthenticated history means no one's questions are private; any visitor can read, continue, rename or delete any thread. Threads are auto-titled from their first question and can be renamed by anyone. Thread deletion is permanent with no undo and no record of who performed it. There is no retention or expiry policy for conversations.

**Related:** US-013, US-014, US-015, US-016

### EPIC-005 · approved · source: requirements:EPIC-005

The app shell and operational guardrails (open access, rate limiting, setup) that make an unauthenticated, internet-reachable tool workable for a small trusted team.

No login or shared password gate exists; anyone with the URL can read and change everything. Per-IP rate limiting on chat and upload endpoints, plus the document cap, is the only protection for the operator's Gemini quota. Gemini powers both answers and embeddings on a single server-side key; there is no billing anywhere in the product. Interface is English-only with light/neutral styling, responsive browser-only (no native apps). No fixed deadline was given; 'usable soon' was assumed.

**Related:** US-017, US-018, US-019, US-020, US-021

- ⚠ No fixed delivery deadline was provided; 'usable soon' is an assumption, not a commitment.

### US-001 · approved · source: requirements:US-001

Team members can upload one or more PDF, DOCX or TXT/Markdown files from the browser into the shared library so their content becomes available to ask questions about. Priority: critical.

AC-001: selecting/dragging several supported files and confirming upload accepts and stores each, immediately showing status 'processing' in the shared library. AC-002: files of unsupported type (e.g. XLSX, PPTX) are rejected before upload with a message naming supported formats, and no library entry is created. AC-003: files over ~25MB are rejected with a size-limit message while other valid files in the same selection still upload. AC-004: if one file in a batch fails to upload, the rest continue and the failure is reported individually rather than aborting the whole batch.

**Related:** EPIC-001

### US-002 · approved · source: requirements:US-002

Uploaded documents are extracted, chunked with overlap, and embedded by Gemini in the background so users don't wait on screen. Priority: critical.

AC-005: on successful upload, background processing extracts text, splits it into overlapping chunks, requests Gemini embeddings, and stores chunks, embeddings and source location (file name + page/section). AC-006: processing continues server-side even if the browser is closed, until the document reaches a final status. AC-007: on completion, status becomes 'ready' and chunks become retrievable by chat. AC-008: if Gemini errors or is unavailable and retries are exhausted, the document is marked 'failed' with a short reason, and no partial/orphaned chunks remain in the index.

**Related:** EPIC-001, US-001, US-003

- ⚠ The number of retries and backoff policy before a document is marked 'failed' (AC-008) is not specified.

### US-003 · approved · source: requirements:US-003

Users can see whether each upload is processing, ready, or failed, with progress, so they know when they can ask questions or when something went wrong. Priority: high.

AC-009: a document being indexed shows a 'processing' state with progress that updates without manual page reload. AC-010: a failed document shows status 'failed' with a human-readable reason (e.g. 'no extractable text found', 'embedding service error'). AC-011: scanned/image-only PDFs that yield no usable text are marked 'failed' with a reason indicating no text could be extracted and that scanned documents are unsupported, contributing nothing to chat answers.

**Related:** EPIC-001, US-002

- ⚠ Mechanism for live progress updates on the documents screen (e.g. polling vs. push) is not specified, notable given no queue/cache service is in the stack.

### US-004 · approved · source: requirements:US-004

All team members see every uploaded document with its name, size, upload time and indexing status in one shared library. Priority: high.

AC-012: the documents screen lists all documents in the single shared workspace with file name, size, upload date/time and status. AC-013: when no documents exist, an empty state explains that uploading PDF/DOCX/TXT/Markdown is how the assistant learns to answer. AC-014: when another visitor uploads or deletes a document, refreshing/next update shows the same shared list with no per-user filtering.

**Related:** EPIC-002

### US-005 · approved · source: requirements:US-005

Any team member can delete a document so it stops being used in answers, removing outdated or incorrect material from citations. Priority: high.

AC-015: deleting and confirming a permanent-deletion warning removes the document, its stored original file, and all its chunks/embeddings, and it disappears from the library. AC-016: after deletion, no chunk or citation from that document appears in future answers. AC-017: because the app has no accounts, any visitor can delete any document with no restriction, no undo, and no record of who performed it -- agreed open-access behaviour, flagged as an open assumption pending a decision on restricted or recoverable deletion. AC-018: deleting a document still in 'processing' stops/discards its in-flight indexing with no leftover chunks.

**Related:** EPIC-002, US-004

- ⚠ AC-017 explicitly records unrestricted, unrecoverable, unattributed deletion as an open assumption pending a product decision on whether to restrict or allow recovery.

### US-006 · approved · source: requirements:US-006

The library refuses new uploads once a configured total document cap is reached, protecting storage and Gemini quota from being exhausted by any anonymous visitor. Priority: medium.

AC-019: at the configured maximum document count, new uploads are rejected with a message explaining the library is full and an existing document must be deleted first. AC-020: deleting a document when at cap immediately re-enables uploading with no restart or manual intervention. AC-021: the operator-configured cap value is used at app start, with a documented default applying if none is set.

**Related:** EPIC-002

- ⚠ The documented default cap value (used when the operator sets none, per AC-021) is not specified in these requirements.

### US-007 · approved · source: requirements:US-007

Users ask a question in chat and receive an answer built only from the uploaded documents, so they can trust it reflects the team's own material. Priority: critical.

AC-022: with 'ready' documents present, a submitted question retrieves the most relevant chunks from across the whole shared library and generates an answer using only those chunks. AC-023: there is intentionally no control to limit search to particular documents -- every question searches the entire library. AC-024: if no documents exist or none are 'ready', the assistant replies there are no indexed documents to answer from and points to the documents screen, instead of answering from general knowledge. AC-025: on a Gemini API error or timeout, the chat shows a clear error message and the question remains available to retry without corrupting the thread.

**Related:** EPIC-003, US-008, US-009

- ⚠ The retrieval parameters that define 'most relevant chunks' (e.g. top-k, similarity threshold) are not specified in the requirements.

### US-008 · approved · source: requirements:US-008

The assistant tells users plainly when the documents do not contain the answer, so they are never misled by an invented answer. Priority: critical.

AC-026: when retrieval returns no sufficiently relevant chunks, the assistant states the answer was not found in the uploaded documents, with no guessed answer and no citations. AC-027: if retrieved chunks only partially cover the question, the assistant answers the covered part with citations and explicitly states which part is not covered. AC-028: general-knowledge questions unrelated to any uploaded document are declined with the 'not found in the documents' response rather than answered from the model's own knowledge.

**Related:** EPIC-003, US-007

- ⚠ The relevance threshold that decides 'sufficiently relevant' versus 'not found' (AC-026) is not quantified.

### US-009 · approved · source: requirements:US-009

Every answer shows which file and page/section it came from, so users can verify it against the original document. Priority: critical.

AC-029: a produced answer lists source documents used, each showing file name and page number or section identifier. AC-030: when an answer draws on several documents, each distinct source is listed separately and de-duplicated, with no source cited that wasn't actually retrieved for that answer. AC-031: when the assistant replies 'not found in the documents', no citations are shown.

**Related:** EPIC-003, US-007, US-010

### US-010 · approved · source: requirements:US-010

Users can expand a citation to read the exact retrieved excerpt the answer was based on, to judge how well-supported it is. Priority: high.

AC-032: expanding a citation shows the exact retrieved chunk text with its file name and page/section. AC-033: collapsing hides the excerpt again, leaving the answer readable and unchanged. AC-034: if the source document behind a citation has since been deleted, opening an older thread and expanding that citation shows that the source document is no longer in the library, rather than an error.

**Related:** EPIC-003, US-009

### US-011 · approved · source: requirements:US-011

Answers appear progressively, token by token, so users get immediate feedback instead of waiting on a spinner. Priority: high.

AC-035: once Gemini begins generating, text appears progressively in the chat rather than only on completion. AC-036: when generation finishes, citations are displayed and the completed message with citations is persisted to the thread. AC-037: if the connection drops mid-stream, reopening the thread shows either the completed stored answer or a clear indication that the answer did not complete, with the ability to ask again.

**Related:** EPIC-003, US-007

### US-012 · approved · source: requirements:US-012

Follow-up questions take the thread's earlier turns into account so users can reference prior context without repeating themselves. Priority: high.

AC-038: a follow-up using a pronoun or implicit reference includes the thread's prior turns when interpreting the question and retrieving chunks, resolving the reference correctly. AC-039: a brand-new thread applies no context from any other thread; the assistant answers only on the new thread's own content. AC-040: in a long thread, a further follow-up stays within the model's context limit by including the most recent relevant turns, and the answer is still produced successfully.

**Related:** EPIC-003, US-007

- ⚠ The specific context-window/truncation policy for including 'most recent relevant turns' (AC-040) is not defined numerically.

### US-022 · approved · source: requirements:US-022

Chat message bubbles for the user's questions and the assistant's answers are correctly and consistently aligned for readability across devices. Priority: low.

AC-071: user messages are consistently aligned to one side and assistant messages to the other, with no overlap or misaligned edges. AC-072: during token-by-token streaming, the bubble keeps correct alignment while growing/resizing. AC-073: bubbles with citations or long wrapped content remain correctly aligned and sized without overflowing the chat column. AC-074: on narrow mobile browsers, bubbles remain aligned and readable without horizontal scrolling. AC-075: reopening a long existing thread displays every historical bubble, old and new, with the corrected alignment.

**Related:** EPIC-003

- ⚠ Which side (left/right) is designated for user vs. assistant messages is not specified.

### US-013 · approved · source: requirements:US-013

A sidebar lists all conversation threads the team has had, so users can find and reuse earlier answers instead of asking again. Priority: high.

AC-041: the sidebar lists all threads in the shared workspace, most recently active first, each showing its title. AC-042: because the app has no accounts and history is shared, every visitor sees every other visitor's threads with no filtering and no privacy -- agreed open-access behaviour, recorded as an open assumption. AC-043: with no conversations yet, the sidebar shows an empty state and a new conversation can be started immediately.

**Related:** EPIC-004

- ⚠ AC-042 records fully shared, unfiltered thread visibility (no privacy) as an open assumption rather than a finalized decision.

### US-014 · approved · source: requirements:US-014

Users can start a new conversation or open and continue any existing one, including threads started by someone else. Priority: high.

AC-044: choosing 'new conversation' opens an empty thread, persisted to the shared list once its first question is sent. AC-045: opening an existing thread loads its full question-and-answer history, including each answer's citations, in order. AC-046: sending a new question in someone else's thread appends it to that same shared thread, visible to everyone, using the thread's earlier turns as context. AC-047: reloading the browser or opening from another device still shows the thread and messages, since history is stored server-side.

**Related:** EPIC-004, US-013

### US-015 · approved · source: requirements:US-015

Each thread is automatically named from its first question so it can be recognized in the sidebar without manual naming. Priority: medium.

AC-048: sending the first question in a new thread generates a short title derived from it, shown in the sidebar. AC-049: a very long first question produces a title truncated to a readable length without breaking the layout. AC-050: once auto-titled, the title does not change automatically as further questions are asked.

**Related:** EPIC-004, US-014

- ⚠ The exact title-generation method and truncation length (AC-049) are not specified.

### US-016 · approved · source: requirements:US-016

Any team member can rename a thread to something clearer or delete it when no longer useful, keeping the shared sidebar tidy. Priority: medium.

AC-051: renaming any thread, including one started by someone else, stores the new title server-side and shows it to every visitor. AC-052: an empty-title rename is rejected and the previous title is kept. AC-053: deleting any thread and confirming the permanent-deletion warning removes the thread and all its messages for everyone, with no undo and no record of who deleted it -- agreed open-access behaviour, recorded as an open assumption. AC-054: deleting the thread currently being viewed returns the chat area to an empty/new conversation state rather than a broken thread.

**Related:** EPIC-004, US-013

- ⚠ AC-053 records unrestricted, unrecoverable, unattributed thread deletion as an open assumption pending a product decision.

### US-017 · approved · source: requirements:US-017

Anyone with the link can use the app immediately with no sign-up, login, or password, removing friction for a small trusted internal team. Priority: critical.

AC-055: opening the URL lands directly in the shared workspace with full access to chat, history and documents, with no sign-up, login or shared-password prompt. AC-056: different people on different machines see exactly the same documents and conversation threads, with no per-person data separation. AC-057: any unknown visitor who finds the URL can also read, upload and delete everything -- the accepted risk of the agreed open-access model, recorded as an open assumption.

**Related:** EPIC-005

- ⚠ AC-057 records the full open-access risk (any finder of the URL has full read/write/delete access) as an accepted but still-open assumption.

### US-018 · approved · source: requirements:US-018

A responsive two-area layout (chat with thread sidebar, and documents) is usable on both laptop and phone browsers. Priority: high.

AC-058: on desktop, the chat screen shows the thread sidebar alongside it, and switching to the documents screen does not lose the open thread. AC-059: on narrow mobile browsers, the sidebar, chat and documents areas are each reachable and usable without horizontal scrolling. AC-060: all labels, statuses and messages are in English, rendered in the agreed neutral/light style, with no language switcher.

**Related:** EPIC-005

### US-019 · approved · source: requirements:US-019

Server-side per-IP rate limits on chat and upload endpoints protect the operator's Gemini quota from being exhausted by a stranger who finds the URL. Priority: high.

AC-061: exceeding the configured per-IP chat limit within the configured window rejects further chat requests with a 'too many requests, try again shortly' message and makes no Gemini call. AC-062: exceeding the configured per-IP upload limit similarly rejects further uploads with a clear message and stores/embeds nothing. AC-063: once the limit window elapses, requests from that IP are accepted again automatically. AC-064: normal use by the expected 5-25 person team does not trigger the limits, and limit values are operator-configurable.

**Related:** EPIC-005

- ⚠ Concrete rate-limit values (requests per window, window length) are not specified, only that they are configurable (AC-064).

### US-020 · approved · source: requirements:US-020

Setup notes cover the GEMINI_API_KEY and how to run and deploy the app, so the operator can get it running without guesswork. Priority: high.

AC-065: setup notes list every required configuration value -- GEMINI_API_KEY, the database/pgvector connection, object storage, the document cap, and rate-limit settings -- and how to set each. AC-066: following the documented steps from a clean environment starts the app locally and allows uploading a document and getting a cited answer. AC-067: a missing or invalid GEMINI_API_KEY surfaces a clear configuration error naming the missing/rejected key, rather than a generic failure. AC-068: GEMINI_API_KEY is server-side only and never exposed to the browser; all Gemini calls for answers and embeddings are made from the server.

**Related:** EPIC-005

### US-021 · approved · source: requirements:US-021

The app runs as a free internal tool with no payments, plans, subscriptions or usage billing anywhere in the product. Priority: low.

AC-069: no screen of the app shows pricing, plans, paywalls, quota-purchase or payment elements. AC-070: Gemini usage incurred by chat and embedding calls is charged solely to the operator's own Gemini account, and the app bills no one -- recorded as the agreed assumption that costs sit on the operator.

**Related:** EPIC-005
<!-- sdlc:auto:end narrative -->

<!-- sdlc:auto:start summary -->
**Requirements version:** v2  
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
<!-- sdlc:auto:end epics -->
