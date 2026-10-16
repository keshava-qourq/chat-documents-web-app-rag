"""Thread and message endpoints: shared conversations and chat.

Everything here runs in one shared workspace -- there is no owner column and
no per-caller filtering anywhere in this module, and no route requires
authentication. Grounded answer generation (retrieval, the Gemini call, SSE
streaming, persisting an assistant message with citations) is a later story;
this module persists the user's turn and hands it to `app.services
.request_answer`, the seam that story fills in.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.config import rate_limit_chat_per_minute
from app.database import get_db
from app.models import Message, Thread
from app.rate_limit import limiter
from app.schemas import (
    MessageCreateRequest,
    MessageOut,
    ThreadCreated,
    ThreadDetail,
    ThreadRenameRequest,
    ThreadRenameResponse,
    ThreadSummary,
)
from app.services import derive_title, request_answer

router = APIRouter(tags=["threads"])

_THREAD_NOT_FOUND = "Thread not found"


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
        messages=[MessageOut.model_validate(m) for m in messages],
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


@router.post("/threads/{thread_id}/messages", response_model=MessageOut)
@limiter.limit(lambda: f"{rate_limit_chat_per_minute()}/minute")
async def post_message(
    thread_id: uuid.UUID,
    body: MessageCreateRequest,
    request: Request,
    db: Session = Depends(get_db),  # noqa: B008
) -> Message:
    thread = db.get(Thread, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail=_THREAD_NOT_FOUND)

    earlier_messages = (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    context = [{"role": m.role, "content": m.content} for m in earlier_messages]

    message = Message(thread_id=thread.id, role="user", content=body.question)
    db.add(message)

    if not earlier_messages:
        thread.title = derive_title(body.question)

    thread.last_active_at = datetime.now(UTC)

    db.commit()
    db.refresh(message)

    request_answer(body.question, context)

    return message
