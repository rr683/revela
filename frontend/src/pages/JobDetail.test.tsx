import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import JobDetail from "./JobDetail";
import type { Job } from "../types";

// Mock the API client
vi.mock("../api/client", () => ({
  getJob: vi.fn(),
  deleteJob: vi.fn(),
  listOutputs: vi.fn(),
  getOutputUrl: vi.fn((jobId: string, name: string) => `/mock/${jobId}/${name}`),
}));

// Mock ModelViewer since it needs WebGL
vi.mock("../components/ModelViewer", () => ({
  default: ({ filename }: { filename: string }) => (
    <div data-testid="model-viewer">{filename}</div>
  ),
}));

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

import { getJob, listOutputs } from "../api/client";

function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: "detail-job-abcdef",
    status: "completed",
    method: "splatfacto",
    created_at: "2025-01-15T10:30:00Z",
    updated_at: "2025-01-15T10:35:00Z",
    started_at: "2025-01-15T10:30:05Z",
    completed_at: "2025-01-15T10:35:00Z",
    error_message: null,
    input_video: "scene.mp4",
    input_image_dir: null,
    num_frames: 120,
    duration_seconds: 295.3,
    quality: { psnr: 28.5, ssim: 0.9421 },
    outputs: null,
    ...overrides,
  };
}

function renderWithRoute(jobId: string) {
  return render(
    <MemoryRouter initialEntries={[`/jobs/${jobId}`]}>
      <Routes>
        <Route path="/jobs/:jobId" element={<JobDetail />} />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("JobDetail", () => {
  it("shows loading state initially", () => {
    vi.mocked(getJob).mockReturnValue(new Promise(() => {}));
    renderWithRoute("detail-job-abcdef");

    expect(screen.getByText("Loading job...")).toBeInTheDocument();
  });

  it("renders job metadata when loaded", async () => {
    const job = makeJob();
    vi.mocked(getJob).mockResolvedValue(job);
    vi.mocked(listOutputs).mockResolvedValue([]);

    renderWithRoute("detail-job-abcdef");

    await waitFor(() => {
      expect(screen.getByText("detail-job-a")).toBeInTheDocument();
    });

    expect(screen.getByText("Completed", { selector: ".status-badge" })).toBeInTheDocument();
    expect(screen.getByText("splatfacto")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText(/295\.3/)).toBeInTheDocument();
    expect(screen.getByText(/28\.50/)).toBeInTheDocument();
    expect(screen.getByText("0.9421")).toBeInTheDocument();
  });

  it("shows progress bar for running jobs", async () => {
    const job = makeJob({ status: "training", completed_at: null, quality: null });
    vi.mocked(getJob).mockResolvedValue(job);

    renderWithRoute("training-job");

    await waitFor(() => {
      expect(
        screen.getByText("Training 3D reconstruction model..."),
      ).toBeInTheDocument();
    });
  });

  it("shows error banner for failed jobs", async () => {
    const job = makeJob({
      status: "failed",
      error_message: "CUDA out of memory",
      completed_at: null,
      quality: null,
    });
    vi.mocked(getJob).mockResolvedValue(job);

    renderWithRoute("failed-job");

    await waitFor(() => {
      expect(screen.getByText("CUDA out of memory")).toBeInTheDocument();
    });
  });

  it("renders output files with download links for completed jobs", async () => {
    const job = makeJob();
    const outputs = [
      { name: "model.ply", path: "/out/model.ply", size_bytes: 5242880, suffix: ".ply" },
      { name: "cameras.json", path: "/out/cameras.json", size_bytes: 2048, suffix: ".json" },
    ];
    vi.mocked(getJob).mockResolvedValue(job);
    vi.mocked(listOutputs).mockResolvedValue(outputs);

    renderWithRoute("detail-job-abcdef");

    await waitFor(() => {
      // model.ply appears in both the output list and the mocked ModelViewer
      expect(screen.getAllByText("model.ply").length).toBeGreaterThanOrEqual(1);
      expect(screen.getByText("cameras.json")).toBeInTheDocument();
    });

    expect(screen.getByText("5.0 MB")).toBeInTheDocument();
    expect(screen.getByText("2.0 KB")).toBeInTheDocument();

    const downloadLinks = screen.getAllByText("Download");
    expect(downloadLinks).toHaveLength(2);
  });

  it("auto-selects first PLY file for 3D viewer", async () => {
    const job = makeJob();
    const outputs = [
      { name: "cameras.json", path: "/out/cameras.json", size_bytes: 2048, suffix: ".json" },
      { name: "scene.ply", path: "/out/scene.ply", size_bytes: 1024, suffix: ".ply" },
    ];
    vi.mocked(getJob).mockResolvedValue(job);
    vi.mocked(listOutputs).mockResolvedValue(outputs);

    renderWithRoute("detail-job-abcdef");

    await waitFor(() => {
      expect(screen.getByTestId("model-viewer")).toBeInTheDocument();
      expect(screen.getByTestId("model-viewer")).toHaveTextContent("scene.ply");
    });
  });

  it("shows error banner when API fails", async () => {
    vi.mocked(getJob).mockRejectedValue(new Error("Server error"));

    renderWithRoute("bad-job");

    await waitFor(() => {
      expect(screen.getByText("Server error")).toBeInTheDocument();
    });
  });

  it("hides delete button while job is running", async () => {
    const job = makeJob({ status: "preprocessing", completed_at: null, quality: null });
    vi.mocked(getJob).mockResolvedValue(job);

    renderWithRoute("running-job");

    await waitFor(() => {
      expect(screen.getByText("Preprocessing")).toBeInTheDocument();
    });

    expect(screen.queryByText("Delete Job")).not.toBeInTheDocument();
  });

  it("shows delete button for completed jobs", async () => {
    const job = makeJob();
    vi.mocked(getJob).mockResolvedValue(job);
    vi.mocked(listOutputs).mockResolvedValue([]);

    renderWithRoute("detail-job-abcdef");

    await waitFor(() => {
      expect(screen.getByText("Delete Job")).toBeInTheDocument();
    });
  });
});
