import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "./Dashboard";
import type { Job } from "../types";

// Mock the API client
vi.mock("../api/client", () => ({
  listJobs: vi.fn(),
  createJob: vi.fn(),
  deleteJob: vi.fn(),
}));

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

import { listJobs, deleteJob } from "../api/client";

function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: "test-job-1",
    status: "completed",
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

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Dashboard", () => {
  it("shows loading state initially", () => {
    vi.mocked(listJobs).mockReturnValue(new Promise(() => {})); // never resolves
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText("Loading...")).toBeInTheDocument();
  });

  it("renders header and upload section", async () => {
    vi.mocked(listJobs).mockResolvedValue({ jobs: [], total: 0 });

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(screen.getByText("Revela")).toBeInTheDocument();
    expect(
      screen.getByText("Video & Image to 3D Reconstruction"),
    ).toBeInTheDocument();
    expect(screen.getByText("New Reconstruction")).toBeInTheDocument();
  });

  it("shows empty state when no jobs exist", async () => {
    vi.mocked(listJobs).mockResolvedValue({ jobs: [], total: 0 });

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(
        screen.getByText(/No reconstruction jobs yet/),
      ).toBeInTheDocument();
    });
  });

  it("renders job cards when jobs exist", async () => {
    const jobs = [
      makeJob({ id: "job-aaa-bbb-ccc", method: "splatfacto" }),
      makeJob({ id: "job-ddd-eee-fff", method: "nerfacto", status: "training" }),
    ];
    vi.mocked(listJobs).mockResolvedValue({ jobs, total: 2 });

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("job-aaa-bbb-")).toBeInTheDocument();
      expect(screen.getByText("job-ddd-eee-")).toBeInTheDocument();
    });

    expect(screen.getByText("(2)")).toBeInTheDocument();
  });

  it("shows error banner when API call fails", async () => {
    vi.mocked(listJobs).mockRejectedValue(new Error("Network error"));

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("Network error")).toBeInTheDocument();
    });
  });

  it("removes job from list after successful delete", async () => {
    const jobs = [makeJob({ id: "job-to-delete-x" })];
    vi.mocked(listJobs).mockResolvedValue({ jobs, total: 1 });
    vi.mocked(deleteJob).mockResolvedValue(undefined);

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByText("job-to-delet")).toBeInTheDocument();
    });
  });
});
