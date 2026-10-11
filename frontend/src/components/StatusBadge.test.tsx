import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { JobStatus } from "../types";
import { StatusBadge } from "./StatusBadge";

const STATUSES: JobStatus[] = [
  "queued",
  "running",
  "succeeded",
  "failed",
  "retrying",
  "cancelled",
];

describe("status badges", () => {
  it("includes a text label for every state", () => {
    for (const status of STATUSES) {
      const { unmount } = render(<StatusBadge status={status} />);
      const expected = status.charAt(0).toUpperCase() + status.slice(1);
      expect(screen.getByText(expected)).toBeInTheDocument();
      unmount();
    }
  });
});
