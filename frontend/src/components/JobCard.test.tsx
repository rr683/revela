import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import JobCard from "./JobCard";
import type { Job } from "../types";

function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: "abc-123-def-456",
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

describe("JobCard", () => {
  it("renders job ID (truncated), method, and status", () => {
    const job = makeJob();
    render(<JobCard job={job} onView={vi.fn()} onDelete={vi.fn()} />);

    expect(screen.getByText("abc-123-def-")).toBeInTheDocument();
    expect(screen.getByText("splatfacto")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
  });

  it("shows frame count when present", () => {
    const job = makeJob({ num_frames: 120 });
    render(<JobCard job={job} onView={vi.fn()} onDelete={vi.fn()} />);

    expect(screen.getByText("120 frames")).toBeInTheDocument();
  });

  it("shows duration when present", () => {
    const job = makeJob({ duration_seconds: 42.7 });
    render(<JobCard job={job} onView={vi.fn()} onDelete={vi.fn()} />);

    expect(screen.getByText("42.7s processing")).toBeInTheDocument();
  });

  it("shows error message when present", () => {
    const job = makeJob({ status: "failed", error_message: "GPU OOM" });
    render(<JobCard job={job} onView={vi.fn()} onDelete={vi.fn()} />);

    expect(screen.getByText("GPU OOM")).toBeInTheDocument();
  });

  it("calls onView when card is clicked", async () => {
    const user = userEvent.setup();
    const onView = vi.fn();
    const job = makeJob();
    render(<JobCard job={job} onView={onView} onDelete={vi.fn()} />);

    await user.click(screen.getByText("View"));
    expect(onView).toHaveBeenCalledWith("abc-123-def-456");
  });

  it("calls onDelete when delete button is clicked", async () => {
    const user = userEvent.setup();
    const onDelete = vi.fn();
    const job = makeJob({ status: "completed" });
    render(<JobCard job={job} onView={vi.fn()} onDelete={onDelete} />);

    await user.click(screen.getByText("Delete"));
    expect(onDelete).toHaveBeenCalledWith("abc-123-def-456");
  });

  it("hides delete button while job is running", () => {
    for (const status of ["preprocessing", "pose_estimation", "training", "exporting"] as const) {
      const { unmount } = render(
        <JobCard job={makeJob({ status })} onView={vi.fn()} onDelete={vi.fn()} />,
      );
      expect(screen.queryByText("Delete")).not.toBeInTheDocument();
      unmount();
    }
  });

  it("shows delete button for terminal states", () => {
    for (const status of ["completed", "failed", "cancelled", "pending"] as const) {
      const { unmount } = render(
        <JobCard job={makeJob({ status })} onView={vi.fn()} onDelete={vi.fn()} />,
      );
      expect(screen.getByText("Delete")).toBeInTheDocument();
      unmount();
    }
  });
});
