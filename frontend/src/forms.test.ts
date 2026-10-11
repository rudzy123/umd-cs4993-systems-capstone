import { describe, expect, it } from "vitest";

import { buildSubmission, parseEdges, parseNumbers } from "./forms";

describe("form parsers", () => {
  it("parses comma-separated numbers", () => {
    expect(parseNumbers("3, 1, 2")).toEqual([3, 1, 2]);
  });

  it("rejects a non-numeric token", () => {
    expect(parseNumbers("1, no")).toMatch(/not a finite number/);
  });

  it("rejects a negative edge weight", () => {
    expect(parseEdges("A B -1")).toMatch(/zero or positive/);
  });

  it("rejects fibonacci above the limit before any request", () => {
    const result = buildSubmission({
      jobType: "fibonacci",
      numbers: "",
      nodes: "",
      edges: "",
      source: "",
      target: "",
      directed: true,
      text: "",
      topN: "10",
      fibonacciN: "10001",
    });
    expect(result.ok).toBe(false);
  });
});
