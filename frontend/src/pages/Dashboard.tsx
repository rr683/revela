import { useState } from "react";
import { useNavigate } from "react-router-dom";
import FileUpload from "../components/FileUpload";
import JobCard from "../components/JobCard";
import { createJob, deleteJob } from "../api/client";
import { useJobs } from "../context/JobsContext";

export default function Dashboard() {
  const { jobs, loading, error: contextError, removeJob, addJob } = useJobs();
  const [uploading, setUploading] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const navigate = useNavigate();

  const error = localError || contextError;

  const handleUpload = async (
    files: { video?: File; images?: File[] },
    method: string,
  ) => {
    setUploading(true);
    setLocalError(null);
    try {
      const job = await createJob(files, { method });
      addJob(job);
      navigate(`/jobs/${job.id}`);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (jobId: string) => {
    try {
      await deleteJob(jobId);
      removeJob(jobId);
    } catch (e) {
      setLocalError(e instanceof Error ? e.message : "Delete failed");
    }
  };

  const handleView = (jobId: string) => navigate(`/jobs/${jobId}`);

  return (
    <div className="dashboard">
      <header className="page-header">
        <h1>Revela</h1>
        <p className="subtitle">Video & Image to 3D Reconstruction</p>
      </header>

      <section className="section">
        <h2>New Reconstruction</h2>
        <FileUpload onSubmit={handleUpload} disabled={uploading} />
      </section>

      {error && <div className="error-banner">{error}</div>}

      <section className="section">
        <h2>Jobs {jobs.length > 0 && <span className="count">({jobs.length})</span>}</h2>

        {loading && <p className="loading">Loading...</p>}

        {!loading && jobs.length === 0 && (
          <p className="empty-state">
            No reconstruction jobs yet. Upload a video or images above to get
            started.
          </p>
        )}

        <div className="job-grid">
          {jobs.map((job) => (
            <JobCard
              key={job.id}
              job={job}
              onView={handleView}
              onDelete={handleDelete}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
