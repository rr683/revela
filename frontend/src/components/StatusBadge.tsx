import type { JobStatus } from "../types";

const STATUS_LABELS: Record<JobStatus, string> = {
  pending: "Pending",
  preprocessing: "Preprocessing",
  pose_estimation: "Estimating Poses",
  training: "Training",
  exporting: "Exporting",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

export default function StatusBadge({ status }: { status: JobStatus }) {
  return <span className={`status-badge ${status}`}>{STATUS_LABELS[status]}</span>;
}
