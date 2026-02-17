import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import FileUpload from "../components/FileUpload";
import JobCard from "../components/JobCard";
import { createJob, deleteJob, listJobs } from "../api/client";
import type { Job } from "../types";

export default function Dashboard() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const fetchJobs = useCallback(async () => {
    try {
      const resp = await listJobs();
      setJobs(resp.jobs);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  // Poll every 5s for status updates
  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 5000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const handleUpload = async (
    files: { video?: File; images?: File[] },
    method: string,
  ) => {
    setUploading(true);
    setError(null);
    try {
      const job = await createJob(files, { method });
      navigate(`/jobs/${job.id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async (jobId: string) => {
    try {
      await deleteJob(jobId);
      setJobs((prev) => prev.filter((j) => j.id !== jobId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Delete failed");
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
