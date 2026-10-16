/// <reference types="vite/client" />
// Without the reference above, `import.meta.env` is not typed and `tsc --noEmit` fails --
// which `vite build` does not catch, because it tree-shakes this module out when no screen
// imports it yet.
//
// Where the generated API lives.
//
// Set at build time: the platform bakes the deployed API URL into the frontend build. The
// fallback is the local backend so a bare `npm run dev` still points somewhere real.
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/**
 * A failed API call, carrying the HTTP status and (when the backend sent one)
 * the FastAPI-style `{"detail": "..."}` body alongside the generic message.
 * Screens that need to distinguish *why* a call failed -- e.g. the chat
 * screen telling a "no documents indexed yet" rejection apart from a plain
 * server error -- read `status`/`detail` rather than parsing `message`.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    let detail = "";
    try {
      const body = (await response.json()) as { detail?: unknown };
      detail = typeof body?.detail === "string" ? body.detail : "";
    } catch {
      // No JSON body (or an unparsable one) -- detail stays empty.
    }
    throw new ApiError(
      response.status,
      detail,
      `${init?.method ?? "GET"} ${path} failed: ${response.status}`,
    );
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}

// --- documents ----------------------------------------------------------------

export type DocumentStatusValue = "processing" | "ready" | "failed";

export interface DocumentRecord {
  id: string;
  file_name: string;
  size_bytes: number;
  uploaded_at: string;
  status: DocumentStatusValue;
  progress: number;
  failure_reason: string | null;
  chunk_count: number;
}

export interface DocumentAccepted {
  id: string;
  file_name: string;
  size_bytes: number;
  mime_type: string;
  status: DocumentStatusValue;
  uploaded_at: string;
}

export interface DocumentRejected {
  file_name: string;
  reason: string;
}

export interface UploadResponse {
  accepted: DocumentAccepted[];
  rejected: DocumentRejected[];
}

export interface DocumentStatus {
  id: string;
  status: DocumentStatusValue;
  progress: number;
  failure_reason: string | null;
}

export function listDocuments(): Promise<DocumentRecord[]> {
  return apiFetch<DocumentRecord[]>("/documents");
}

export function getDocumentStatus(id: string): Promise<DocumentStatus> {
  return apiFetch<DocumentStatus>(`/documents/${id}/status`);
}

export function deleteDocument(id: string): Promise<void> {
  return apiFetch<void>(`/documents/${id}`, { method: "DELETE" });
}

/**
 * Multipart upload. Deliberately bypasses `apiFetch`: that helper always
 * stamps a `Content-Type: application/json` header, and a multipart request
 * must let the browser set its own `Content-Type` (with the boundary) by
 * leaving the header unset entirely.
 */
export async function uploadDocuments(files: File[]): Promise<UploadResponse> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const response = await fetch(`${API_BASE_URL}/documents`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(`POST /documents failed: ${response.status}`);
  }
  return (await response.json()) as UploadResponse;
}

// --- threads and messages ------------------------------------------------------

export interface ThreadSummary {
  id: string;
  title: string;
  last_active_at: string;
}

export interface ThreadCreated {
  id: string;
  title: string;
  created_at: string;
}

export interface ThreadRenameResponse {
  id: string;
  title: string;
}

export interface CitationRecord {
  id: string;
  document_name: string;
  source_location: string | null;
  excerpt: string;
}

export interface MessageRecord {
  id: string;
  role: string;
  content: string;
  status: string;
  citations: CitationRecord[];
}

export interface ThreadDetail {
  id: string;
  title: string;
  messages: MessageRecord[];
}

export interface MessageStreamFinal {
  message_id: string;
  citations: CitationRecord[];
}

export function listThreads(): Promise<ThreadSummary[]> {
  return apiFetch<ThreadSummary[]>("/threads");
}

export function createThread(): Promise<ThreadCreated> {
  return apiFetch<ThreadCreated>("/threads", { method: "POST" });
}

export function getThread(id: string): Promise<ThreadDetail> {
  return apiFetch<ThreadDetail>(`/threads/${id}`);
}

export function renameThread(id: string, title: string): Promise<ThreadRenameResponse> {
  return apiFetch<ThreadRenameResponse>(`/threads/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export function deleteThread(id: string): Promise<void> {
  return apiFetch<void>(`/threads/${id}`, { method: "DELETE" });
}

export function postMessage(id: string, question: string): Promise<MessageStreamFinal> {
  return apiFetch<MessageStreamFinal>(`/threads/${id}/messages`, {
    method: "POST",
    body: JSON.stringify({ question }),
  });
}

/**
 * Whether a failed `postMessage` call failed because the shared library has
 * no indexed documents to search, rather than some other server error.
 *
 * Mocked pending CHAT8EED1A-12-2: the backend does not yet implement
 * grounded answer generation (`app.services.request_answer` is a no-op
 * stub), so this contract -- HTTP 422 with `detail: "NO_DOCUMENTS_INDEXED"`
 * -- is this screen's expectation of what that story will return, not yet
 * an observed response. Update this check if the landed contract differs.
 */
export function isNoDocumentsIndexedError(error: unknown): boolean {
  return (
    error instanceof ApiError && error.status === 422 && error.detail === "NO_DOCUMENTS_INDEXED"
  );
}
