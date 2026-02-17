import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import StatusBadge from "./StatusBadge";
import type { JobStatus } from "../types";

describe("StatusBadge", () => {
  const statuses: [JobStatus, string][] = [
    ["pending", "Pending"],
    ["preprocessing", "Preprocessing"],
    ["pose_estimation", "Estimating Poses"],
    ["training", "Training"],
    ["exporting", "Exporting"],
    ["completed", "Completed"],
    ["failed", "Failed"],
    ["cancelled", "Cancelled"],
  ];

  it.each(statuses)("renders %s as '%s'", (status, label) => {
    render(<StatusBadge status={status} />);
    const badge = screen.getByText(label);
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveClass("status-badge", status);
  });
});
