import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { JobsProvider, useJobs } from "./JobsContext";
import type { Job } from "../types";

// Mock the API client
vi.mock("../api/client", () => ({
  listJobs: vi.fn(),
  getJob: vi.fn(),
}));

// Mock the WebSocket hook
vi.mock("../hooks/useJobsWebSocket", () => ({
  default: vi.fn(),
}));

import useJobsWebSocket from "../hooks/useJobsWebSocket";
const mockUseJobsWebSocket = vi.mocked(useJobsWebSocket);

import { listJobs } from "../api/client";

function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: "ctx-job-1",
    status: "pending",
    method: "splatfacto",
    created_at: "2025-01-15T10:30:00Z",
    updated_at: "2025-01-15T10:35:00Z",
    started_at: null,
    completed_at: null,
    error_message: null,
    input_video: null,
    input_image_dir: null,
    num_frames: null,
    duration_seconds: null,
    quality: null,
    outputs: null,
    ...overrides,
  };
}

function TestConsumer() {
  const { jobs, loading, error, connected, addJob, removeJob } = useJobs();
  return (
    <div>
      <span data-testid="loading">{String(loading)}</span>
      <span data-testid="error">{error ?? "none"}</span>
      <span data-testid="connected">{String(connected)}</span>
      <span data-testid="count">{jobs.length}</span>
      <ul data-testid="job-list">
        {jobs.map((j) => (
          <li key={j.id} data-testid={`job-${j.id}`}>
            {j.id}:{j.status}
          </li>
        ))}
      </ul>
      <button data-testid="add-job" onClick={() => addJob(makeJob({ id: "added-job" }))}>
        Add
      </button>
      <button data-testid="remove-job" onClick={() => removeJob("ctx-job-1")}>
        Remove
      </button>
    </div>
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseJobsWebSocket.mockImplementation(() => {});
});

describe("JobsContext", () => {
  it("starts in loading state", () => {
    vi.mocked(listJobs).mockReturnValue(new Promise(() => {}));

    render(
      <JobsProvider>
        <TestConsumer />
      </JobsProvider>,
    );

    expect(screen.getByTestId("loading")).toHaveTextContent("true");
    expect(screen.getByTestId("count")).toHaveTextContent("0");
  });

  it("loads jobs on mount", async () => {
    const jobs = [makeJob({ id: "job-a" }), makeJob({ id: "job-b" })];
    vi.mocked(listJobs).mockResolvedValue({ jobs, total: 2 });

    render(
      <JobsProvider>
        <TestConsumer />
      </JobsProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });

    expect(screen.getByTestId("count")).toHaveTextContent("2");
  });

  it("sets error on fetch failure", async () => {
    vi.mocked(listJobs).mockRejectedValue(new Error("Network failure"));

    render(
      <JobsProvider>
        <TestConsumer />
      </JobsProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("error")).toHaveTextContent("Network failure");
    });
  });

  it("addJob inserts into state", async () => {
    vi.mocked(listJobs).mockResolvedValue({ jobs: [], total: 0 });

    render(
      <JobsProvider>
        <TestConsumer />
      </JobsProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("loading")).toHaveTextContent("false");
    });

    act(() => {
      screen.getByTestId("add-job").click();
    });

    expect(screen.getByTestId("count")).toHaveTextContent("1");
  });

  it("removeJob deletes from state", async () => {
    vi.mocked(listJobs).mockResolvedValue({
      jobs: [makeJob({ id: "ctx-job-1" })],
      total: 1,
    });

    render(
      <JobsProvider>
        <TestConsumer />
      </JobsProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("count")).toHaveTextContent("1");
    });

    act(() => {
      screen.getByTestId("remove-job").click();
    });

    expect(screen.getByTestId("count")).toHaveTextContent("0");
  });

  it("passes onJobUpdate callback to WebSocket hook", async () => {
    vi.mocked(listJobs).mockResolvedValue({ jobs: [], total: 0 });

    render(
      <JobsProvider>
        <TestConsumer />
      </JobsProvider>,
    );

    await waitFor(() => {
      expect(mockUseJobsWebSocket).toHaveBeenCalled();
    });

    const { onJobUpdate, onConnect, onDisconnect } = mockUseJobsWebSocket.mock.calls[0][0];
    expect(typeof onJobUpdate).toBe("function");
    expect(typeof onConnect).toBe("function");
    expect(typeof onDisconnect).toBe("function");
  });

  it("updates job in state when WebSocket delivers update", async () => {
    const initialJob = makeJob({ id: "ws-job", status: "pending" });
    vi.mocked(listJobs).mockResolvedValue({ jobs: [initialJob], total: 1 });

    render(
      <JobsProvider>
        <TestConsumer />
      </JobsProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("job-ws-job")).toHaveTextContent("ws-job:pending");
    });

    // Simulate WS update
    const { onJobUpdate } = mockUseJobsWebSocket.mock.calls[0][0];
    act(() => {
      onJobUpdate({ ...initialJob, status: "training" });
    });

    expect(screen.getByTestId("job-ws-job")).toHaveTextContent("ws-job:training");
  });

  it("throws when useJobs is called outside provider", () => {
    // Suppress console.error for expected error
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => render(<TestConsumer />)).toThrow(
      "useJobs must be used within a JobsProvider",
    );

    spy.mockRestore();
  });
});
