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
  /**
   * Whether the source document is still in the shared library. Absent on
   * older/mocked data, which is treated as available (`true`) so existing
   * fixtures keep working.
   */
  document_available?: boolean;
}

export type MessageStatusValue = "complete" | "incomplete";

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
  /**
   * `null` when the backend's `final` event covers the "no documents
   * indexed yet" case: `app.services.request_answer` streams its canned
   * reply back as ordinary `token` events but deliberately never persists
   * it as a message (there is nothing grounded to save), so there is no
   * message id to report. `postMessage` below translates that shape into
   * an `ApiError` the caller already knows how to handle, so this is never
   * actually seen outside this module.
   */
  message_id: string | null;
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

/**
 * Parses one `event:`/`data:` block out of a raw SSE record (the text
 * between two `\n\n` separators). Returns `null` for a block with no
 * `data:` line (e.g. a bare comment/keepalive).
 */
function parseSseRecord(raw: string): { event: string; data: string } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join("\n") };
}

/**
 * Posts a question and streams the answer back over SSE (via `fetch` +
 * `ReadableStream` -- no event-source dependency, per constraint).
 *
 * `token` events call `onToken` with the incremental text as it arrives so
 * the caller can render progressively (AC-035). The `final` event's payload
 * is returned once the stream ends -- unless it reports `message_id: null`,
 * which is how the backend represents "the shared library has no indexed
 * documents yet" (see `MessageStreamFinal`): that case is raised as an
 * `ApiError(422, "NO_DOCUMENTS_INDEXED", ...)` instead of resolving, so
 * callers only ever need `isNoDocumentsIndexedError` to tell it apart from
 * a real answer. An `error` event, a non-2xx response (e.g. 429 rate
 * limiting), or a dropped connection all reject the promise too; callers
 * that already rendered partial tokens are responsible for deciding what to
 * keep on screen.
 */
export async function postMessage(
  id: string,
  question: string,
  onToken?: (text: string) => void,
): Promise<MessageStreamFinal> {
  const response = await fetch(`${API_BASE_URL}/threads/${id}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
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
      `POST /threads/${id}/messages failed: ${response.status}`,
    );
  }

  if (!response.body) {
    throw new Error("Streaming response had no body.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let finalResult: MessageStreamFinal | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let separatorIndex: number;
    while ((separatorIndex = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, separatorIndex);
      buffer = buffer.slice(separatorIndex + 2);
      const record = parseSseRecord(raw);
      if (!record) continue;

      let payload: unknown;
      try {
        payload = JSON.parse(record.data);
      } catch {
        continue;
      }

      if (record.event === "token") {
        const text = (payload as { text?: string }).text ?? "";
        if (text) onToken?.(text);
      } else if (record.event === "final") {
        finalResult = payload as MessageStreamFinal;
      } else if (record.event === "error") {
        const detail = (payload as { detail?: string }).detail ?? "Something went wrong.";
        throw new Error(detail);
      }
    }
  }

  if (!finalResult) {
    throw new Error("The connection dropped before the answer finished.");
  }
  if (finalResult.message_id === null) {
    throw new ApiError(422, "NO_DOCUMENTS_INDEXED", "No documents are indexed yet.");
  }
  return finalResult;
}

/**
 * Whether a failed `postMessage` call failed because the shared library has
 * no indexed documents to search, rather than some other server error.
 *
 * Matches the shape `postMessage` raises when the backend's `final` SSE
 * event reports `message_id: null` -- `app.services.request_answer`'s
 * canned, ungrounded reply for a library with no `'ready'` document yet.
 */
export function isNoDocumentsIndexedError(error: unknown): boolean {
  return (
    error instanceof ApiError && error.status === 422 && error.detail === "NO_DOCUMENTS_INDEXED"
  );
}
