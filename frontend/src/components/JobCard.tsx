import type { Job } from "../types";
import StatusBadge from "./StatusBadge";

interface JobCardProps {
  job: Job;
  onView: (id: string) => void;
  onDelete: (id: string) => void;
}

export default function JobCard({ job, onView, onDelete }: JobCardProps) {
  const isRunning = ["preprocessing", "pose_estimation", "training", "exporting"].includes(
    job.status,
  );
  const canDelete = !isRunning;

  return (
    <div className={`job-card ${job.status}`} onClick={() => onView(job.id)}>
      <div className="job-card-header">
        <code className="job-id">{job.id.slice(0, 12)}</code>
        <StatusBadge status={job.status} />
      </div>

      <div className="job-card-body">
        <div className="job-meta">
          <span className="method-tag">{job.method}</span>
          <span className="job-date">
            {new Date(job.created_at).toLocaleString()}
          </span>
        </div>

        {job.num_frames && (
          <p className="job-detail">{job.num_frames} frames</p>
        )}
        {job.duration_seconds && (
          <p className="job-detail">
            {job.duration_seconds.toFixed(1)}s processing
          </p>
        )}
        {job.error_message && (
          <p className="job-error">{job.error_message}</p>
        )}
      </div>

      <div className="job-card-actions">
        <button className="btn-secondary" onClick={() => onView(job.id)}>
          View
        </button>
        {canDelete && (
          <button
            className="btn-danger"
            onClick={(e) => {
              e.stopPropagation();
              onDelete(job.id);
            }}
          >
            Delete
          </button>
        )}
      </div>
    </div>
  );
}
