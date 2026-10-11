import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { JobForm } from "./JobForm";

describe("job form", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("exposes labeled controls", () => {
    render(
      <MemoryRouter>
        <JobForm onCreated={() => undefined} />
      </MemoryRouter>,
    );
    expect(screen.getByLabelText("Job type")).toBeInTheDocument();
    expect(screen.getByLabelText("Numbers")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit job" })).toBeEnabled();
  });

  it("shows a validation alert and does not call the API", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MemoryRouter>
        <JobForm onCreated={() => undefined} />
      </MemoryRouter>,
    );
    await user.selectOptions(screen.getByLabelText("Job type"), "fibonacci");
    await user.clear(screen.getByLabelText("Fibonacci n"));
    await user.type(screen.getByLabelText("Fibonacci n"), "10001");
    await user.click(screen.getByRole("button", { name: "Submit job" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/10000/);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
