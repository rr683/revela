import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { deleteJob, getJob, getOutputUrl, listOutputs } from "../api/client";
import StatusBadge from "../components/StatusBadge";
import ModelViewer from "../components/ModelViewer";
import type { Job, OutputFile } from "../types";

export default function JobDetail() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const [job, setJob] = useState<Job | null>(null);
  const [outputs, setOutputs] = useState<OutputFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<OutputFile | null>(null);
  const [error, setError] = useState<string | null>(null);

  const isRunning = job
    ? ["pending", "preprocessing", "pose_estimation", "training", "exporting"].includes(
        job.status,
      )
    : false;

  useEffect(() => {
    if (!jobId) return;
    let active = true;

    const poll = async () => {
      try {
        const j = await getJob(jobId);
        if (!active) return;
        setJob(j);
        setError(null);

        if (j.status === "completed") {
          const outs = await listOutputs(jobId);
          if (active) {
            setOutputs(outs);
            // Auto-select best viewable file (prefer GLB > PLY > OBJ)
            if (!selectedFile) {
              const viewable =
                outs.find((f) => f.suffix === ".glb" || f.suffix === ".gltf") ||
                outs.find((f) => f.suffix === ".ply" || f.suffix === ".obj" || f.suffix === ".stl");
              if (viewable) setSelectedFile(viewable);
            }
          }
        }
      } catch (e) {
        if (active) {
          setError(e instanceof Error ? e.message : "Failed to load job");
        }
      }
    };

    poll();
    const interval = setInterval(poll, isRunning ? 3000 : 15000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, [jobId, isRunning]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleDelete = async () => {
    if (!jobId) return;
    try {
      await deleteJob(jobId);
      navigate("/");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  };

  if (error) {
    return (
      <div className="page">
        <button className="btn-back" onClick={() => navigate("/")}>
          &larr; Back
        </button>
        <div className="error-banner">{error}</div>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="page">
        <p className="loading">Loading job...</p>
      </div>
    );
  }

  return (
    <div className="page job-detail">
      <button className="btn-back" onClick={() => navigate("/")}>
        &larr; Back
      </button>

      <div className="detail-header">
        <div>
          <h1>
            Job <code>{job.id.slice(0, 12)}</code>
          </h1>
          <StatusBadge status={job.status} />
          <span className="method-tag">{job.method}</span>
        </div>
        {!isRunning && (
          <button className="btn-danger" onClick={handleDelete}>
            Delete Job
          </button>
        )}
      </div>

      {/* Progress indicator for running jobs */}
      {isRunning && (
        <div className="progress-section">
          <div className="progress-bar">
            <div
              className={`progress-fill ${job.status}`}
              style={{ width: progressPercent(job.status) + "%" }}
            />
          </div>
          <p className="progress-label">
            {STATUS_MESSAGES[job.status] || job.status}
          </p>
        </div>
      )}

      {/* Error display */}
      {job.error_message && (
        <div className="error-banner">{job.error_message}</div>
      )}

      {/* Metadata */}
      <div className="detail-grid">
        <div className="detail-item">
          <label>Created</label>
          <span>{new Date(job.created_at).toLocaleString()}</span>
        </div>
        {job.started_at && (
          <div className="detail-item">
            <label>Started</label>
            <span>{new Date(job.started_at).toLocaleString()}</span>
          </div>
        )}
        {job.completed_at && (
          <div className="detail-item">
            <label>Completed</label>
            <span>{new Date(job.completed_at).toLocaleString()}</span>
          </div>
        )}
        {job.num_frames && (
          <div className="detail-item">
            <label>Frames</label>
            <span>{job.num_frames}</span>
          </div>
        )}
        {job.duration_seconds && (
          <div className="detail-item">
            <label>Processing Time</label>
            <span>{job.duration_seconds.toFixed(1)}s</span>
          </div>
        )}
        {job.quality?.psnr && (
          <div className="detail-item">
            <label>PSNR</label>
            <span>{job.quality.psnr.toFixed(2)} dB</span>
          </div>
        )}
        {job.quality?.ssim && (
          <div className="detail-item">
            <label>SSIM</label>
            <span>{job.quality.ssim.toFixed(4)}</span>
          </div>
        )}
      </div>

      {/* 3D Viewer */}
      {selectedFile && jobId && (
        <section className="section">
          <h2>3D Viewer</h2>
          <ModelViewer
            url={getOutputUrl(jobId, selectedFile.name)}
            filename={selectedFile.name}
          />
        </section>
      )}

      {/* Output files */}
      {outputs.length > 0 && (
        <section className="section">
          <h2>Output Files</h2>
          <div className="output-list">
            {outputs.map((f) => (
              <div
                key={f.path}
                className={`output-item ${selectedFile?.path === f.path ? "selected" : ""}`}
              >
                <div className="output-info" onClick={() => setSelectedFile(f)}>
                  <span className="output-name">{f.name}</span>
                  <span className="output-size">{formatBytes(f.size_bytes)}</span>
                </div>
                <a
                  className="btn-secondary"
                  href={getOutputUrl(jobId!, f.name)}
                  download={f.name}
                >
                  Download
                </a>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

const STATUS_MESSAGES: Record<string, string> = {
  pending: "Waiting in queue...",
  preprocessing: "Extracting and filtering frames...",
  pose_estimation: "Estimating camera poses with COLMAP...",
  training: "Training 3D reconstruction model...",
  exporting: "Exporting 3D model...",
};

function progressPercent(status: string): number {
  const map: Record<string, number> = {
    pending: 5,
    preprocessing: 20,
    pose_estimation: 40,
    training: 70,
    exporting: 90,
    completed: 100,
  };
  return map[status] ?? 0;
}
