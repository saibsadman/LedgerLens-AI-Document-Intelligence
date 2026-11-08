export const API_URL = import.meta.env.VITE_API_URL || "/api/v1";

export type Status = "queued" | "processing" | "completed" | "needs_review" | "failed";

export interface DocumentSummary {
  id: string;
  original_name: string;
  extension: string;
  size_bytes: number;
  status: Status;
  progress: number;
  page_count: number | null;
  needs_review: boolean;
  created_at: string;
  updated_at: string;
}

export interface ValidationIssue {
  id: number;
  code: string;
  field: string | null;
  severity: "error" | "warning";
  message: string;
  expected: string | null;
  actual: string | null;
}

export interface DocumentDetail extends DocumentSummary {
  mime_type: string | null;
  checksum_sha256: string;
  raw_text: string | null;
  structured_data: Record<string, unknown> | null;
  confidence: Record<string, number> | null;
  error_message: string | null;
  completed_at: string | null;
  validations: ValidationIssue[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(body.detail || `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  list: (query = "", reviewOnly = false) => request<{items: DocumentSummary[]; total: number}>(`/documents?q=${encodeURIComponent(query)}${reviewOnly ? "&needs_review=true" : ""}&page_size=100`),
  get: (id: string) => request<DocumentDetail>(`/documents/${id}`),
  upload: async (files: File[]) => {
    const form = new FormData();
    files.forEach((file) => form.append("files", file));
    return request<{accepted: DocumentSummary[]; rejected: {filename: string; reason: string}[]}>("/documents/upload", { method: "POST", body: form });
  },
  correct: (id: string, updates: Record<string, unknown>) => request<DocumentDetail>(`/documents/${id}`, { method: "PATCH", headers: {"Content-Type": "application/json"}, body: JSON.stringify({updates, corrected_by: "web-reviewer"}) }),
  reprocess: (id: string) => request<DocumentSummary>(`/documents/${id}/reprocess`, {method: "POST"}),
  compare: (left: string, right: string) => request<{matches: boolean; comparisons: {field: string; left: unknown; right: unknown; matches: boolean}[]}>("/documents/compare", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({left_document_id: left, right_document_id: right})}),
};

