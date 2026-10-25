# API Reference

> Maintained by QuorQ AI SDLC. Text between `sdlc:auto` markers is regenerated; anything outside them is yours and is kept.

<!-- sdlc:auto:start endpoints -->
| Method | Path | Handler | Source | Summary |
|---|---|---|---|---|
| GET | /documents | list_documents | `backend/app/routers/documents.py:139` | — |
| POST | /documents | upload_documents | `backend/app/routers/documents.py:62` | — |
| DELETE | /documents/{document_id} | delete_document | `backend/app/routers/documents.py:166` | — |
| GET | /documents/{document_id}/status | get_document_status | `backend/app/routers/documents.py:144` | — |
| GET | /health | health | `backend/app/main.py:115` | Liveness probe, and the only route here that is not a stub. |
| GET | /threads | list_threads | `backend/app/routers/threads.py:65` | — |
| POST | /threads | create_thread | `backend/app/routers/threads.py:70` | — |
| DELETE | /threads/{thread_id} | delete_thread | `backend/app/routers/threads.py:129` | — |
| GET | /threads/{thread_id} | get_thread | `backend/app/routers/threads.py:79` | — |
| PATCH | /threads/{thread_id} | rename_thread | `backend/app/routers/threads.py:110` | — |
| POST | /threads/{thread_id}/messages | post_message | `backend/app/routers/threads.py:143` | — |
<!-- sdlc:auto:end endpoints -->

<!-- sdlc:auto:start drift -->
**Designed but missing:**

- DELETE /documents/{id}
- DELETE /threads/{id}
- GET /documents/{id}/status
- GET /threads/{id}
- PATCH /threads/{id}
- POST /threads/{id}/messages

**Code only:**

- DELETE /documents/{document_id}
- DELETE /threads/{thread_id}
- GET /documents/{document_id}/status
- GET /threads/{thread_id}
- PATCH /threads/{thread_id}
- POST /threads/{thread_id}/messages
<!-- sdlc:auto:end drift -->

<!-- sdlc:auto:start source -->
Generated from commit `f7e4d16`
<!-- sdlc:auto:end source -->
