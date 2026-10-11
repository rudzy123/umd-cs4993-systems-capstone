import type { ApiErrorBody, Job, JobList } from "./types";

export class ApiError extends Error {
  status: number;
  code: string;
  details: { loc: string[]; message: string }[];

  constructor(status: number, code: string, message: string, details: { loc: string[]; message: string }[]) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function apiBase(): string {
  const configured = import.meta.env.VITE_API_BASE_URL ?? "/api";
  return configured.replace(/\/$/, "");
}

export function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.details.length === 0) {
      return error.message;
    }
    return error.details.map((detail) => `${detail.loc.join(".")}: ${detail.message}`).join(" ");
  }
  return "The lab could not reach the API.";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });
  if (!response.ok) {
    let payload: ApiErrorBody | null = null;
    try {
      payload = (await response.json()) as ApiErrorBody;
    } catch {
      payload = null;
    }
    throw new ApiError(
      response.status,
      payload?.error.code ?? "http_error",
      payload?.error.message ?? "Request failed.",
      payload?.error.details ?? [],
    );
  }
  return (await response.json()) as T;
}

export function createJob(jobType: string, input: Record<string, unknown>): Promise<Job> {
  return request<Job>("/jobs", {
    method: "POST",
    body: JSON.stringify({ job_type: jobType, input }),
  });
}

export function listJobs(): Promise<JobList> {
  return request<JobList>("/jobs?limit=20");
}

export function getJob(id: string): Promise<Job> {
  return request<Job>(`/jobs/${id}`);
}

export function cancelJob(id: string): Promise<Job> {
  return request<Job>(`/jobs/${id}/cancel`, { method: "POST" });
}
