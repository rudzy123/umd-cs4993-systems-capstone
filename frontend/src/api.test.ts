import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, createJob, errorText, listJobs } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("api client", () => {
  it("posts a job and reads the identifier", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ id: "abc", status: "queued" }), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const job = await createJob("sort", { numbers: [1, 2] });
    expect(job.id).toBe("abc");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://api.test/jobs",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("turns an error payload into an ApiError", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              error: {
                code: "validation_error",
                message: "The request is invalid.",
                details: [{ loc: ["input", "n"], message: "too large" }],
              },
            }),
            { status: 422, headers: { "Content-Type": "application/json" } },
          ),
        ),
      ),
    );
    try {
      await listJobs();
      expect.unreachable();
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect(errorText(error)).toContain("input.n");
    }
  });
});
