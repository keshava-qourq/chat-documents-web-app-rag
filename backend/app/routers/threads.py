"""Thread and message endpoints: shared conversations and chat.

Generated from the approved API spec. Every handler here is a stub that
returns a typed placeholder -- retrieval, grounded generation, SSE streaming
and persisting the answer with de-duplicated citations are the development
sprint's work. The chat rate limit is part of the endpoint contract itself
(architecture note: reject with 429 before any Gemini call), so it is wired
in now rather than left for later.
"""

import uuid

from fastapi import APIRouter, Request

from app.config import rate_limit_chat_per_minute
from app.rate_limit import limiter
from app.schemas import StubResponse

router = APIRouter(tags=["threads"])


@router.get("/threads", response_model=StubResponse)
async def list_threads() -> StubResponse:
    return StubResponse(endpoint="GET /threads")


@router.post("/threads", response_model=StubResponse)
async def create_thread() -> StubResponse:
    return StubResponse(endpoint="POST /threads")


@router.get("/threads/{thread_id}", response_model=StubResponse)
async def get_thread(thread_id: uuid.UUID) -> StubResponse:
    return StubResponse(endpoint="GET /threads/{id}")


@router.patch("/threads/{thread_id}", response_model=StubResponse)
async def rename_thread(thread_id: uuid.UUID) -> StubResponse:
    return StubResponse(endpoint="PATCH /threads/{id}")


@router.delete("/threads/{thread_id}", response_model=StubResponse)
async def delete_thread(thread_id: uuid.UUID) -> StubResponse:
    return StubResponse(endpoint="DELETE /threads/{id}")


@router.post("/threads/{thread_id}/messages", response_model=StubResponse)
@limiter.limit(lambda: f"{rate_limit_chat_per_minute()}/minute")
async def post_message(thread_id: uuid.UUID, request: Request) -> StubResponse:
    return StubResponse(endpoint="POST /threads/{id}/messages")
