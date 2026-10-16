"""Thread and message endpoints: shared conversations and chat.

Everything here runs in one shared workspace -- there is no owner column and
no per-caller filtering anywhere in this module, and no route requires
authentication. `POST /threads/{id}/messages` streams its grounded answer as
Server-Sent Events: `app.services.request_answer` is the seam that does the
retrieval, the streaming Gemini call, and persisting the completed (or
interrupted) assistant turn; this module's job is to validate the request,
persist the user's turn, and hand both the question and the thread's own
prior turns to that seam before returning its generator as the stream body.

Posting a question never depends on any document already being indexed:
`request_answer` itself covers the empty-library case (and the
nothing-above-threshold case) by yielding its own canned, ungrounded answer
without ever calling Gemini -- so the user's turn is always persisted and
the thread is always usable, whether or not the shared library has anything
in it yet.

When a `'ready'` document *does* exist, answering the question requires a
real Gemini call (retrieval's embedding call, then generation), so a missing
`GEMINI_API_KEY` is checked for here -- before the user's turn is persisted,
before `request_answer` is ever called, and therefore before any Gemini SDK
call or file store happens -- and rejected with the operator-facing 503
config-error shape, rather than being discovered deep inside the SSE stream
where a structured JSON error can no longer be returned (a stream already in
progress cannot change its status code).
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.orm import Session

from app.config import gemini_api_key, rate_limit_chat_per_minute
from app.database import get_db
from app.models import Message, Thread
from app.rate_limit import limiter
from app.schemas import (
    CitationOut,
    MessageCreateRequest,
    MessageOut,
    ThreadCreated,
    ThreadDetail,
    ThreadRenameRequest,
    ThreadRenameResponse,
    ThreadSummary,
)
from app.services import derive_title, has_ready_documents, request_answer

router = APIRouter(tags=["threads"])

_THREAD_NOT_FOUND = "Thread not found"

GEMINI_NOT_CONFIGURED_DETAIL = {
    "code": "gemini_not_configured",
    "message": (
        "GEMINI_API_KEY is not set. Set it in the server's environment "
        "(see README.md) to enable chat answers."
    ),
}


@router.get("/threads", response_model=list[ThreadSummary])
async def list_threads(db: Session = Depends(get_db)) -> list[Thread]:  # noqa: B008
    return db.query(Thread).order_by(Thread.last_active_at.desc()).all()


@router.post("/threads", response_model=ThreadCreated)
async def create_thread(db: Session = Depends(get_db)) -> Thread:  # noqa: B008
    thread = Thread()
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread


@router.get("/threads/{thread_id}", response_model=ThreadDetail)
async def get_thread(
    thread_id: uuid.UUID,
    db: Session = Depends(get_db),  # noqa: B008
) -> ThreadDetail:
    thread = db.get(Thread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail=_THREAD_NOT_FOUND)

    messages = (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    return ThreadDetail(
        id=thread.id,
        title=thread.title,
        messages=[
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                status=m.status,
                citations=[CitationOut.from_citation(c) for c in m.citations],
            )
            for m in messages
        ],
    )


@router.patch("/threads/{thread_id}", response_model=ThreadRenameResponse)
async def rename_thread(
    thread_id: uuid.UUID,
    body: ThreadRenameRequest,
    db: Session = Depends(get_db),  # noqa: B008
) -> ThreadRenameResponse:
    thread = db.get(Thread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail=_THREAD_NOT_FOUND)

    new_title = body.title.strip()
    if not new_title:
        raise HTTPException(status_code=422, detail="Title must not be empty")

    thread.title = new_title
    db.commit()
    return ThreadRenameResponse(id=thread.id, title=thread.title)


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_thread(
    thread_id: uuid.UUID,
    db: Session = Depends(get_db),  # noqa: B008
) -> Response:
    thread = db.get(Thread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail=_THREAD_NOT_FOUND)

    db.delete(thread)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/threads/{thread_id}/messages")
@limiter.limit(lambda: f"{rate_limit_chat_per_minute()}/minute")
async def post_message(
    thread_id: uuid.UUID,
    body: MessageCreateRequest,
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
) -> StreamingResponse:
    thread = db.get(Thread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail=_THREAD_NOT_FOUND)

    # A real answer needs a real Gemini call (retrieval's embedding, then
    # generation) only once a 'ready' document exists; with none yet,
    # `request_answer` returns its own canned, Gemini-free answer, so there
    # is nothing to configure-check against. Checked -- and rejected, with
    # no Gemini SDK call and no user turn persisted yet -- before anything
    # else happens.
    if has_ready_documents(db) and not gemini_api_key():
        raise HTTPException(status_code=503, detail=GEMINI_NOT_CONFIGURED_DETAIL)

    earlier_messages = (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    history = [{"role": m.role, "content": m.content} for m in earlier_messages]

    message = Message(thread_id=thread.id, role="user", content=body.question)
    db.add(message)

    if not earlier_messages:
        thread.title = derive_title(body.question)

    thread.last_active_at = datetime.now(UTC)

    db.commit()
    db.refresh(message)

    event_stream = request_answer(db, thread, body.question, history)
    return StreamingResponse(event_stream, media_type="text/event-stream")
