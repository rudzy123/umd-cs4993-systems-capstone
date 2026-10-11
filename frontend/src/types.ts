export type JobType = "sort" | "shortest_path" | "word_frequency" | "fibonacci";

export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "retrying"
  | "cancelled";

export interface Attempt {
  attempt_number: number;
  status: string;
  worker_id: string;
  error_summary: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface Job {
  id: string;
  job_type: JobType;
  status: JobStatus;
  input: Record<string, unknown>;
  result: Record<string, unknown> | null;
  error_summary: string | null;
  retry_count: number;
  max_retries: number;
  version: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  attempts: Attempt[];
}

export interface JobList {
  jobs: Job[];
  limit: number;
  offset: number;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details: { loc: string[]; message: string }[];
  };
}

export const JOB_LABELS: Record<JobType, string> = {
  sort: "Sort numbers",
  shortest_path: "Shortest path",
  word_frequency: "Word frequency",
  fibonacci: "Fibonacci",
};

export const STATUS_LABELS: Record<JobStatus, string> = {
  queued: "Queued",
  running: "Running",
  succeeded: "Succeeded",
  failed: "Failed",
  retrying: "Retrying",
  cancelled: "Cancelled",
};

export function isTerminal(status: JobStatus): boolean {
  return status === "succeeded" || status === "failed" || status === "cancelled";
}
