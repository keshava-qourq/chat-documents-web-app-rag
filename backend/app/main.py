"""Application entrypoint.

Generated from the approved architecture: one router per component that owns
endpoints, one route per endpoint the API spec declares. Every generated route
is a stub that returns a typed placeholder, so the service starts, serves its
OpenAPI document and passes its tests before a single handler is implemented.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from app import models  # noqa: F401 -- imported so the tables register before create_all
from app.database import Base, engine
from app.rate_limit import limiter, rate_limit_exceeded_handler
from app.routers import documents, threads
from app.services import configured_services

_TITLE = '"chat documents" web app (RAG'
_DESCRIPTION = (
    'Build a "chat with your documents" web app (RAG chatbot) that uses Google Gemini.\n'
    "There is NO sign-up, NO login and NO user accounts: anyone who opens the app uses one\n"
    "shared workspace. All documents and conversations are visible to everyone using it. "
    "with history"
)

app = FastAPI(
    title=_TITLE,
    description=_DESCRIPTION,
    version="0.1.0",
)

# Per-IP rate limiting on uploads and chat, part of the endpoint contract
# itself -- see app/rate_limit.py. The handler turns a breached limit into the
# 429 the API spec promises -- with the same {"detail": "..."} body every
# other error response in this API uses -- instead of slowapi's own default
# shape or an unhandled exception.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

# The SPA runs on a different origin than the API, so the browser refuses its calls
# unless that origin is allowed here. In development that is the Vite dev server; when
# deployed, the platform injects the frontend's real URL as ALLOWED_ORIGINS (comma
# separated). Point ALLOWED_ORIGINS at the real thing and nothing else has to change.
_dev_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_allowed_origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins or _dev_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(threads.router)

# The `vector` column type needs its Postgres extension enabled before the
# schema that uses it can be created. A no-op on SQLite, which database.py
# defaults to locally so a fresh clone runs without a database server.
if engine.dialect.name == "postgresql":
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

# The scaffold ships no migrations, so the tables are created from the models on
# startup. Replace this with Alembic before anything holds data worth keeping.
Base.metadata.create_all(bind=engine)


@app.get("/health")
async def health() -> dict[str, object]:
    """Liveness probe, and the only route here that is not a stub."""
    return {"status": "ok", "services": configured_services()}
