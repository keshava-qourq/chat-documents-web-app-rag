"""Document library endpoints: upload, list, status and delete.

Generated from the approved API spec. Every handler here is a stub that
returns a typed placeholder -- parsing the multipart upload, validating file
type/size/document cap, storing accepted files and scheduling background
indexing are the development sprint's work. The upload rate limit is part of
the endpoint contract itself (architecture note: reject with 429 before any
file is stored), so it is wired in now rather than left for later.
"""

import uuid

from fastapi import APIRouter, Request

from app.config import rate_limit_uploads_per_hour
from app.rate_limit import limiter
from app.schemas import StubResponse

router = APIRouter(tags=["documents"])


@router.post("/documents", response_model=StubResponse)
@limiter.limit(lambda: f"{rate_limit_uploads_per_hour()}/hour")
async def upload_documents(request: Request) -> StubResponse:
    return StubResponse(endpoint="POST /documents")


@router.get("/documents", response_model=StubResponse)
async def list_documents() -> StubResponse:
    return StubResponse(endpoint="GET /documents")


@router.get("/documents/{document_id}/status", response_model=StubResponse)
async def get_document_status(document_id: uuid.UUID) -> StubResponse:
    return StubResponse(endpoint="GET /documents/{id}/status")


@router.delete("/documents/{document_id}", response_model=StubResponse)
async def delete_document(document_id: uuid.UUID) -> StubResponse:
    return StubResponse(endpoint="DELETE /documents/{id}")
