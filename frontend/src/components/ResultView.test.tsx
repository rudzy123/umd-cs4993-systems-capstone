import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Job } from "../types";
import { ResultView } from "./ResultView";

function sample(overrides: Partial<Job>): Job {
  return {
    id: "job-1",
    job_type: "sort",
    status: "succeeded",
    input: {},
    result: { sorted: [1, 2], comparisons: 1 },
    error_summary: null,
    retry_count: 0,
    max_retries: 2,
    version: 1,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    started_at: null,
    finished_at: "2026-01-01T00:00:01Z",
    attempts: [],
    ...overrides,
  };
}

describe("result view", () => {
  it("shows a failed summary without a stack trace", () => {
    render(
      <ResultView
        job={sample({
          status: "failed",
          result: null,
          error_summary: "The job could not be completed. Please submit it again.",
        })}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("could not be completed");
  });

  it("shows why a cancelled job stopped", () => {
    render(
      <ResultView
        job={sample({
          status: "cancelled",
          result: null,
          error_summary: "Cancelled by user.",
        })}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Cancelled by user.");
  });

  it("shows a successful sort", () => {
    render(<ResultView job={sample({})} />);
    expect(screen.getByText(/1, 2/)).toBeInTheDocument();
  });
});
