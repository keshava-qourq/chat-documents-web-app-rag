"""Document library endpoints: upload, list, status and delete.

Every route here is reachable with no authentication of any kind -- there is
one shared workspace, so there is no owner column and no per-caller
filtering anywhere in this module. Originals are stored in MinIO through
`app.storage`; text extraction, chunking and embedding are a later story, so
`status` stays "processing" for every newly accepted document.
"""

import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app import storage
from app.config import MAX_UPLOAD_FILE_BYTES, document_cap, rate_limit_uploads_per_hour
from app.database import get_db
from app.models import Document
from app.rate_limit import limiter
from app.schemas import (
    DocumentAccepted,
    DocumentOut,
    DocumentRejected,
    DocumentStatusOut,
    UploadResponse,
)

router = APIRouter(tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
_UNSUPPORTED_TYPE_REASON = (
    "Unsupported file type. Supported formats are PDF, DOCX, TXT and Markdown."
)
_TOO_LARGE_REASON = "File exceeds the 25 MB limit."
_STORAGE_FAILURE_REASON = "Could not store file; please try again."


def _cap_full_reason() -> str:
    return (
        f"The library is full ({document_cap()} document limit). "
        "Delete an existing document before uploading a new one."
    )


@router.post("/documents", response_model=UploadResponse)
@limiter.limit(lambda: f"{rate_limit_uploads_per_hour()}/hour")
async def upload_documents(
    request: Request,
    files: list[UploadFile] = File(...),  # noqa: B008
    db: Session = Depends(get_db),  # noqa: B008
) -> UploadResponse:
    accepted: list[DocumentAccepted] = []
    rejected: list[DocumentRejected] = []

    for upload in files:
        file_name = upload.filename or "unnamed"

        # Cap check runs before any extraction, storage write or background
        # task is scheduled -- a full library rejects a file regardless of
        # whether it would otherwise have been valid. Read live so a delete
        # that happened moments ago, or an acceptance earlier in this same
        # batch, is reflected immediately.
        if db.query(Document).count() >= document_cap():
            rejected.append(DocumentRejected(file_name=file_name, reason=_cap_full_reason()))
            await upload.close()
            continue

        extension = Path(file_name).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            rejected.append(DocumentRejected(file_name=file_name, reason=_UNSUPPORTED_TYPE_REASON))
            await upload.close()
            continue

        content = await upload.read()

        if len(content) > MAX_UPLOAD_FILE_BYTES:
            rejected.append(DocumentRejected(file_name=file_name, reason=_TOO_LARGE_REASON))
            await upload.close()
            continue

        guessed_mime_type = mimetypes.guess_type(file_name)[0]
        mime_type = upload.content_type or guessed_mime_type or "application/octet-stream"
        document_id = uuid.uuid4()
        storage_key = f"{document_id}{extension}"

        try:
            storage.put_object(storage_key, content, mime_type)
        except Exception:
            rejected.append(DocumentRejected(file_name=file_name, reason=_STORAGE_FAILURE_REASON))
            await upload.close()
            continue

        document = Document(
            id=document_id,
            file_name=file_name,
            mime_type=mime_type,
            size_bytes=len(content),
            storage_key=storage_key,
            status="processing",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        accepted.append(DocumentAccepted.model_validate(document))
        await upload.close()

    return UploadResponse(accepted=accepted, rejected=rejected)


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(db: Session = Depends(get_db)) -> list[Document]:  # noqa: B008
    return db.query(Document).order_by(Document.uploaded_at.desc()).all()


@router.get("/documents/{document_id}/status", response_model=DocumentStatusOut)
async def get_document_status(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),  # noqa: B008
) -> DocumentStatusOut:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    progress = 100 if document.status in ("ready", "failed") else 0
    return DocumentStatusOut(
        id=document.id,
        status=document.status,
        progress=progress,
        failure_reason=document.failure_reason,
    )


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),  # noqa: B008
) -> Response:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    storage.delete_object(document.storage_key)
    db.delete(document)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
