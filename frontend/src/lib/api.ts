// Thin typed fetch client for the backend REST API. Deliberately dependency-free
// (no axios/react-query) to keep the vertical slice lean; token storage and
// error normalization live here so pages never touch `fetch` directly.

const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const ACCESS_TOKEN_KEY = "masea.access_token";
const REFRESH_TOKEN_KEY = "masea.refresh_token";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}, auth = true): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (auth) {
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_PREFIX}${path}`, { ...options, headers });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string };
      detail = body.detail ?? detail;
    } catch {
      // response had no JSON body; fall back to statusText
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// ---- Auth ----

export interface UserResponse {
  id: string;
  email: string;
  is_active: boolean;
}

export interface TokenPairResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export const authApi = {
  register: (email: string, password: string) =>
    request<UserResponse>(
      "/auth/register",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false,
    ),

  login: (email: string, password: string) =>
    request<TokenPairResponse>(
      "/auth/login",
      { method: "POST", body: JSON.stringify({ email, password }) },
      false,
    ),

  me: () => request<UserResponse>("/auth/me"),
};

// ---- Repositories ----

export type RepositoryStatus = "pending" | "cloning" | "indexing" | "ready" | "failed";

export interface RepositoryResponse {
  id: string;
  name: string;
  source_url: string;
  status: RepositoryStatus;
  status_detail: string | null;
  commit_sha: string | null;
  file_count: number;
  symbol_count: number;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export const repositoriesApi = {
  create: (name: string, sourceUrl: string) =>
    request<RepositoryResponse>("/repositories", {
      method: "POST",
      body: JSON.stringify({ name, source_url: sourceUrl }),
    }),

  list: () => request<RepositoryResponse[]>("/repositories"),

  get: (id: string) => request<RepositoryResponse>(`/repositories/${id}`),
};

// ---- Chat / workflows ----

export interface CitationResponse {
  file_path: string;
  start_line: number;
  end_line: number;
}

export interface WorkflowResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  citations: CitationResponse[];
  prompt_version: string;
  latency_ms: number;
  patch_proposal_id: string | null;
}

export const chatApi = {
  askQuestion: (repositoryId: string, question: string) =>
    request<WorkflowResponse>(`/repositories/${repositoryId}/qa`, {
      method: "POST",
      body: JSON.stringify({ question }),
    }),

  investigateBug: (repositoryId: string, bugDescription: string) =>
    request<WorkflowResponse>(`/repositories/${repositoryId}/bug-investigations`, {
      method: "POST",
      body: JSON.stringify({ bug_description: bugDescription }),
    }),

  proposePatch: (repositoryId: string, taskDescription: string) =>
    request<WorkflowResponse>(`/repositories/${repositoryId}/patch-proposals`, {
      method: "POST",
      body: JSON.stringify({ task_description: taskDescription }),
    }),
};

// ---- Patch proposals ----

export type PatchStatus =
  "pending_approval" | "approved" | "rejected" | "test_run_passed" | "test_run_failed" | "applied";

export interface PatchProposalResponse {
  id: string;
  repository_id: string;
  conversation_id: string;
  diff_text: string;
  target_files: string[];
  rationale: string;
  status: PatchStatus;
  test_command: string | null;
  test_output: string | null;
  decided_by: string | null;
  decided_at: string | null;
  created_at: string;
}

export const patchesApi = {
  get: (id: string) => request<PatchProposalResponse>(`/patch-proposals/${id}`),

  decide: (id: string, decision: "approve" | "reject", reason?: string) =>
    request<PatchProposalResponse>(`/patch-proposals/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, reason }),
    }),
};
