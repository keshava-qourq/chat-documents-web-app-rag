# Developer Guide

> Maintained by QuorQ AI SDLC. Text between `sdlc:auto` markers is regenerated; anything outside them is yours and is kept.

<!-- sdlc:auto:start status -->
_Up to date._
<!-- sdlc:auto:end status -->

<!-- sdlc:auto:start source -->
Generated from commit `f7e4d16` · model `claude-sonnet-5`
<!-- sdlc:auto:end source -->

<!-- sdlc:auto:start overview -->
This is a generated 'chat with your documents' RAG (retrieval-augmented generation) web app with no login/accounts -- a single shared workspace where any visitor can upload documents and chat about them. It is two applications in one repo: a Vite + React 19 single-page frontend (approved screens, currently running on seeded sample data) and a FastAPI 0.115 backend that uploads/chunks/embeds documents via Google Gemini, stores embeddings in Postgres+pgvector (SQLite by default locally), stores original files in object storage (MinIO/S3 via boto3), and answers chat questions by streaming grounded, cited responses over Server-Sent Events.
<!-- sdlc:auto:end overview -->

<!-- sdlc:auto:start prerequisites -->
- Python 3.12 (matches backend/Dockerfile base image)
- Node.js (for Vite 6 / React 19 / TypeScript 5.6 toolchain in frontend/package.json)
- pip
- npm
- Docker and Docker Compose (optional, to run Postgres and MinIO locally via docker-compose.yml)
- A Google Gemini API key (GEMINI_API_KEY) for embeddings and chat generation
<!-- sdlc:auto:end prerequisites -->

<!-- sdlc:auto:start setup -->
1. Clone the repository
2. Copy .env.example to .env and fill in required values (e.g. GEMINI_API_KEY)
3. (Optional) Start Postgres and MinIO locally: docker-compose up -d
4. Backend: cd backend
5. Backend: pip install -r requirements.txt
6. Backend: uvicorn app.main:app --reload
7. Frontend: cd frontend
8. Frontend: npm install
9. Frontend: npm run dev
<!-- sdlc:auto:end setup -->

<!-- sdlc:auto:start run -->
| Name | Command | Description |
|---|---|---|
| backend dev | `uvicorn app.main:app --reload` | Runs the FastAPI backend locally (from backend/) with autoreload; defaults to a local SQLite database (app.db) if DATABASE_URL is not set |
| frontend dev | `npm run dev` | Starts the Vite dev server for the React SPA (from frontend/) |
| frontend build | `npm run build` | Bundles the frontend for production with Vite (does not typecheck) |
| frontend preview | `npm run preview` | Serves the built frontend bundle locally |
| frontend typecheck | `npm run typecheck` | Runs tsc --noEmit over the frontend |
| local infra | `docker-compose up -d` | Starts local Postgres 16 (with pgvector-capable image) and MinIO object storage containers defined in docker-compose.yml |
<!-- sdlc:auto:end run -->

<!-- sdlc:auto:start structure -->
| Path | Purpose |
|---|---|
| `backend/app` | FastAPI application: main entrypoint, config, database, models/schemas, ingestion/chunking/embeddings/generation/retrieval pipeline, storage, rate limiting, and services |
| `backend/app/routers` | API route modules: documents.py (upload/list/status/delete) and threads.py (threads and streaming chat messages) |
| `backend/app/tests` | Backend unit tests colocated with app code |
| `backend/tests` | Additional backend test suite (pytest, run via pytest.ini with testpaths = tests) |
| `frontend/src` | React SPA source: App.tsx (shell/router), main.tsx entrypoint, index.css brand tokens |
| `frontend/src/screens` | One module per approved screen: Chat, Documents, Setup |
| `frontend/src/lib` | Shared frontend code: api.ts (backend API client), ui.tsx/icons.tsx (component/icon vocabulary), brand.ts, navigate.ts |
| `frontend/e2e` | Playwright end-to-end acceptance specs |
| `.github/workflows` | CI/CD: deploy.yml builds/pushes the backend Docker image to ECR and deploys the frontend build to AWS Amplify via OIDC |
| `.quorq` | Platform metadata (handoff.json, prepared.json) from the Quorq AI SDLC platform that generated this codebase |
<!-- sdlc:auto:end structure -->

<!-- sdlc:auto:start conventions -->
- Backend: one router per architecture component that owns endpoints (documents.py, threads.py), registered in main.py
- Backend: Pydantic schemas (schemas.py) mirror SQLAlchemy models (models.py) one-to-one, using from_attributes for ORM-to-response conversion
- Backend: Gemini-specific failures raise typed errors (GeminiNotConfiguredError/GeminiKeyRejectedError) per module, mapped centrally in main.py to a consistent 503 {'detail': {'code', 'message'}} shape
- Backend: no authentication/ownership anywhere -- single shared workspace by design
- Backend: SQLite is the local default (database.py); Postgres+pgvector is used when DATABASE_URL points at it, with the vector column type (EmbeddingVector) degrading to JSON on SQLite
- Backend: chat answers stream as Server-Sent Events (token/final/error events) rather than a single JSON response
- Backend: per-IP rate limiting (slowapi) on upload and chat endpoints, configured in app.rate_limit/app.config
- Frontend: one module per approved screen under src/screens/, with App.tsx as the sole navigation shell and route table
- Frontend: all backend calls go through src/lib/api.ts, which throws a typed ApiError carrying HTTP status and backend detail
- Frontend: build-time env var VITE_API_BASE_URL sets the API origin, defaulting to http://localhost:8000
<!-- sdlc:auto:end conventions -->

<!-- sdlc:auto:start testing -->
| Name | Command | Description |
|---|---|---|
| backend tests | `pytest` | Runs backend unit tests (from backend/; pytest.ini sets testpaths=tests) |
| backend lint | `ruff check .` | Lints the backend Python code |
| backend format | `ruff format .` | Formats the backend Python code |
| frontend unit tests | `npm test` | Runs Vitest component tests colocated with components (jsdom environment) |
| frontend lint | `npm run lint` | Runs ESLint over the whole frontend app; this is the gate the platform runs during development |
| frontend e2e | `npm run test:e2e` | Runs Playwright acceptance specs from frontend/e2e; builds/serves the backend and frontend locally unless E2E_BASE_URL is set |
| frontend e2e browser install | `npm run test:e2e:install` | Installs the Chromium browser Playwright needs before running e2e tests |
<!-- sdlc:auto:end testing -->

<!-- sdlc:auto:start troubleshooting -->
| Problem | Solution |
|---|---|
| Chat requests return 503 with code gemini_not_configured or gemini_key_rejected | Set a valid GEMINI_API_KEY in the backend's environment; this is required once any document reaches 'ready' status, since answering then requires a real Gemini embedding/generation call |
| Frontend calls are blocked by the browser with CORS errors | Ensure the frontend origin is allowed: locally this defaults to localhost/127.0.0.1 ports 5173 and 4173 (main.py); when deployed, set the ALLOWED_ORIGINS env var (comma-separated) on the backend |
| vector extension or pgvector-related errors on startup | Only relevant when DATABASE_URL points at Postgres; main.py runs CREATE EXTENSION IF NOT EXISTS vector automatically on Postgres, but the DB user needs privileges to create extensions. On SQLite (the default) this is a no-op and embeddings are stored as JSON instead |
| npm run build succeeds but the app fails type checking or deployment | npm run build does not typecheck; run npm run typecheck (tsc --noEmit) separately to catch type errors before they surface elsewhere |
| Uploads rejected with 'library is full' or unsupported type/size errors | The backend enforces a document cap, a 25 MB per-file limit, and only allows .pdf, .docx, .txt, .md extensions (see backend/app/routers/documents.py and app/config.py) -- delete existing documents or use a supported file type/size |
<!-- sdlc:auto:end troubleshooting -->
