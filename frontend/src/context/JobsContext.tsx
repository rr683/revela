import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import type { Job } from "../types";
import * as api from "../api/client";
import useJobsWebSocket from "../hooks/useJobsWebSocket";

interface JobsContextType {
  jobs: Job[];
  getJob: (jobId: string) => Job | undefined;
  loading: boolean;
  error: string | null;
  connected: boolean;
  refreshJobs: () => Promise<void>;
  refreshJob: (jobId: string) => Promise<Job>;
  addJob: (job: Job) => void;
  removeJob: (jobId: string) => void;
}

const JobsContext = createContext<JobsContextType | null>(null);

const POLL_INTERVAL_CONNECTED = 30_000;
const POLL_INTERVAL_DISCONNECTED = 5_000;

export function JobsProvider({ children }: { children: ReactNode }) {
  const [jobsMap, setJobsMap] = useState<Map<string, Job>>(new Map());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const pollTimer = useRef<ReturnType<typeof setInterval>>(undefined);

  const jobs = Array.from(jobsMap.values()).sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
  );

  const refreshJobs = useCallback(async () => {
    try {
      const resp = await api.listJobs();
      setJobsMap((prev) => {
        const next = new Map(prev);
        for (const job of resp.jobs) {
          next.set(job.id, job);
        }
        const serverIds = new Set(resp.jobs.map((j) => j.id));
        for (const id of prev.keys()) {
          if (!serverIds.has(id)) next.delete(id);
        }
        return next;
      });
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshJob = useCallback(async (jobId: string) => {
    const job = await api.getJob(jobId);
    setJobsMap((prev) => new Map(prev).set(job.id, job));
    return job;
  }, []);

  const addJob = useCallback((job: Job) => {
    setJobsMap((prev) => new Map(prev).set(job.id, job));
  }, []);

  const removeJob = useCallback((jobId: string) => {
    setJobsMap((prev) => {
      const next = new Map(prev);
      next.delete(jobId);
      return next;
    });
  }, []);

  const getJob = useCallback(
    (jobId: string) => jobsMap.get(jobId),
    [jobsMap],
  );

  const handleJobUpdate = useCallback((job: Job) => {
    setJobsMap((prev) => new Map(prev).set(job.id, job));
  }, []);

  const handleConnect = useCallback(() => setConnected(true), []);
  const handleDisconnect = useCallback(() => setConnected(false), []);

  useJobsWebSocket({
    onJobUpdate: handleJobUpdate,
    onConnect: handleConnect,
    onDisconnect: handleDisconnect,
  });

  // Initial fetch
  useEffect(() => {
    refreshJobs();
  }, [refreshJobs]);

  // Polling fallback: fast when WS is down, slow when connected
  useEffect(() => {
    clearInterval(pollTimer.current);
    const interval = connected
      ? POLL_INTERVAL_CONNECTED
      : POLL_INTERVAL_DISCONNECTED;
    pollTimer.current = setInterval(refreshJobs, interval);
    return () => clearInterval(pollTimer.current);
  }, [connected, refreshJobs]);

  return (
    <JobsContext.Provider
      value={{
        jobs,
        getJob,
        loading,
        error,
        connected,
        refreshJobs,
        refreshJob,
        addJob,
        removeJob,
      }}
    >
      {children}
    </JobsContext.Provider>
  );
}

export function useJobs(): JobsContextType {
  const ctx = useContext(JobsContext);
  if (!ctx) {
    throw new Error("useJobs must be used within a JobsProvider");
  }
  return ctx;
}
