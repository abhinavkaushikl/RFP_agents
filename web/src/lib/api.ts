import type {
  IngestResult,
  MarketResult,
  Profile,
  ProfileListItem,
  Readiness,
  RevisionResult,
  RunSummary,
  SearchHit,
  StoredRun,
  TokenUsage,
} from "./types";

export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";
const KEY_STORAGE = "rfp.apiKey";

export function getApiKey(): string {
  try {
    return localStorage.getItem(KEY_STORAGE) ?? "";
  } catch {
    return "";
  }
}

export function setApiKey(value: string): void {
  try {
    if (value) localStorage.setItem(KEY_STORAGE, value);
    else localStorage.removeItem(KEY_STORAGE);
  } catch {
    /* storage unavailable: key lasts for this page only */
  }
}

export class ApiError extends Error {
  status: number;
  code: string;
  retryAfter: number | null;

  constructor(message: string, status: number, code = "error", retryAfter: number | null = null) {
    super(message);
    this.status = status;
    this.code = code;
    this.retryAfter = retryAfter;
  }
}

export function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const key = getApiKey();
  return key ? { ...extra, "X-API-Key": key } : extra;
}

export async function errorFrom(resp: Response): Promise<ApiError> {
  const retry = resp.headers.get("Retry-After");
  let message = `Request failed with HTTP ${resp.status}`;
  let code = "error";
  try {
    const body = await resp.json();
    if (body?.error?.message) {
      message = body.error.message;
      code = body.error.code ?? code;
    } else if (Array.isArray(body?.detail)) {
      message = body.detail
        .map((d: { loc?: string[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".")}: ${d.msg}`)
        .join("; ");
      code = "invalid_request";
    } else if (typeof body?.detail === "string") {
      message = body.detail;
    }
  } catch {
    /* non-JSON error body */
  }
  if (resp.status === 0 || resp.status >= 502) {
    if (code === "error") message = "The API is not reachable. Check that the server is running.";
  }
  return new ApiError(message, resp.status, code, retry ? Number(retry) : null);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers: authHeaders({
        ...(init.body && !(init.body instanceof FormData) ? { "Content-Type": "application/json" } : {}),
        ...((init.headers as Record<string, string>) ?? {}),
      }),
    });
  } catch {
    throw new ApiError("The API is not reachable. Check that the server is running.", 0, "network");
  }
  if (!resp.ok) {
    const err = await errorFrom(resp);
    // The session expired mid-use: go back to the login page and return here afterwards.
    if (err.code === "auth_required" && window.location.pathname !== "/login") {
      window.location.assign("/login");
    }
    throw err;
  }
  return (await resp.json()) as T;
}

const json = (body: unknown) => JSON.stringify(Object.fromEntries(
  Object.entries(body as Record<string, unknown>).filter(([, v]) => v !== undefined && v !== null && v !== ""),
));

export interface AuthUser {
  id: string;
  email: string;
  name: string;
}

export interface AuthState {
  user: AuthUser | null;
  auth_required: boolean;
  signup_enabled: boolean;
}

export const api = {
  me: () => request<AuthState>("/auth/me"),
  login: (email: string, password: string) =>
    request<{ user: AuthUser }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  signup: (name: string, email: string, password: string) =>
    request<{ user: AuthUser }>("/auth/signup", { method: "POST", body: JSON.stringify({ name, email, password }) }),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  ready: async (): Promise<Readiness> => {
    const resp = await fetch(`${API_BASE}/health/ready`, { headers: authHeaders() }).catch(() => null);
    if (!resp) throw new ApiError("The API is not reachable.", 0, "network");
    return (await resp.json()) as Readiness;
  },
  profiles: () => request<{ default: string; profiles: ProfileListItem[] }>("/profiles"),
  profile: (name: string) => request<Profile>(`/profiles/${encodeURIComponent(name)}`),
  runs: (limit = 20, workflowType?: string) =>
    request<{ runs: RunSummary[] }>(`/workflow-runs?limit=${limit}${workflowType ? `&workflow_type=${workflowType}` : ""}`),
  run: <T,>(id: string) => request<StoredRun<T>>(`/workflow-runs/${id}`),
  revise: (sectionId: string, body: { instruction: string; section_key?: string; base_text?: string; requirements?: string[]; profile?: string }) =>
    request<RevisionResult>(`/generated-sections/${sectionId}/revise`, { method: "POST", body: json(body) }),
  revisions: (sectionId: string) =>
    request<{ revisions: { revision_id: string; revision_number: number; instruction: string | null; summary: string | null; draft_text: string; created_at: string | null }[] }>(
      `/generated-sections/${sectionId}/revisions`,
    ),
  marketResearch: (body: { offerings: string[]; requirement_summary?: string; industry?: string; max_companies?: number; profile?: string }) =>
    request<MarketResult>("/market-research-runs", { method: "POST", body: json(body) }),
  extractText: (file: File, profile?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (profile) form.append("profile", profile);
    return request<{ file_name: string; characters: number; text: string; sections: string[] }>("/documents/extract-text", {
      method: "POST",
      body: form,
    });
  },
  uploadProposals: (files: File[], fields: Record<string, string | undefined>) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    Object.entries(fields).forEach(([k, v]) => v && form.append(k, v));
    return request<IngestResult>("/historical-proposals/upload", { method: "POST", body: form });
  },
  ingestRecords: (records: unknown[], sourceName: string, profile?: string) =>
    request<IngestResult>("/historical-proposals/ingest", { method: "POST", body: json({ records, source_name: sourceName, profile }) }),
  search: (body: { query: string; section_type?: string; industry?: string; top_k?: number; profile?: string }) =>
    request<{ results: SearchHit[] }>("/retrieval/search", { method: "POST", body: json(body) }),
  usageSummary: (days: number) => request<TokenUsage>(`/usage/summary?days=${days}`),
  workflowUsage: (id: string) => request<TokenUsage>(`/usage/workflows/${id}`),
  download: async (id: string, format: "pdf" | "md") => {
    const resp = await fetch(`${API_BASE}/workflow-runs/${id}/export?format=${format}`, { headers: authHeaders() });
    if (!resp.ok) throw await errorFrom(resp);
    const blob = await resp.blob();
    const name = /filename="([^"]+)"/.exec(resp.headers.get("Content-Disposition") ?? "")?.[1] ?? `proposal.${format}`;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1500);
  },
};
