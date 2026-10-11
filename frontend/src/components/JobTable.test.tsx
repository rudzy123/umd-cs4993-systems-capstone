import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { Job } from "../types";
import { JobTable } from "./JobTable";

const job: Job = {
  id: "job-1",
  job_type: "sort",
  status: "queued",
  input: { numbers: [1] },
  result: null,
  error_summary: null,
  retry_count: 0,
  max_retries: 2,
  version: 1,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  started_at: null,
  finished_at: null,
  attempts: [],
};

describe("job table", () => {
  it("shows an empty state", () => {
    render(
      <MemoryRouter>
        <JobTable jobs={[]} loading={false} error={null} />
      </MemoryRouter>,
    );
    expect(screen.getByText(/No jobs yet/)).toBeInTheDocument();
  });

  it("shows a loading state", () => {
    render(
      <MemoryRouter>
        <JobTable jobs={null} loading error={null} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("status")).toHaveTextContent("Loading jobs…");
  });

  it("shows an error state", () => {
    render(
      <MemoryRouter>
        <JobTable jobs={null} loading={false} error="The lab could not reach the API." />
      </MemoryRouter>,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("could not reach");
  });

  it("renders status text in a captioned table", () => {
    render(
      <MemoryRouter>
        <JobTable jobs={[job]} loading={false} error={null} />
      </MemoryRouter>,
    );
    expect(screen.getByRole("table", { name: "Recent jobs" })).toBeInTheDocument();
    expect(screen.getByText("Queued")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View job" })).toHaveAttribute("href", "/jobs/job-1");
  });
});
