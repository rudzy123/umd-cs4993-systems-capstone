import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { HomePage } from "./HomePage";

describe("home page accessibility", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ jobs: [], limit: 20, offset: 0 }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
  });

  it("has one heading, a labeled form, and an empty recent-jobs state", async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Submit a job" })).toBeInTheDocument();
    expect(screen.getByLabelText("Job type")).toHaveAccessibleDescription(/Merge sort/);
    expect(await screen.findByText(/No jobs yet/)).toBeInTheDocument();
  });
});
