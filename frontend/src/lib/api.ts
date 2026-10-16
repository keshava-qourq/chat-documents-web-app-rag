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

export async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${response.status}`);
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
