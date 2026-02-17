import type { Job, JobListResponse, OutputFile } from "../types";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, init);
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new ApiError(resp.status, body.detail || resp.statusText);
  }
  return resp.json();
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

export async function createJob(
  files: { video?: File; images?: File[] },
  options: { method?: string; maxIterations?: number } = {},
): Promise<Job> {
  const form = new FormData();

  if (files.video) {
    form.append("video", files.video);
  }
  if (files.images) {
    for (const img of files.images) {
      form.append("images", img);
    }
  }
  form.append("method", options.method || "splatfacto");
  if (options.maxIterations) {
    form.append("max_iterations", String(options.maxIterations));
  }

  return request<Job>("/api/jobs", { method: "POST", body: form });
}

export async function listJobs(
  status?: string,
  limit = 50,
  offset = 0,
): Promise<JobListResponse> {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return request<JobListResponse>(`/api/jobs?${params}`);
}

export async function getJob(jobId: string): Promise<Job> {
  return request<Job>(`/api/jobs/${jobId}`);
}

export async function deleteJob(jobId: string): Promise<void> {
  await request(`/api/jobs/${jobId}`, { method: "DELETE" });
}

export async function listOutputs(jobId: string): Promise<OutputFile[]> {
  return request<OutputFile[]>(`/api/jobs/${jobId}/outputs`);
}

export function getOutputUrl(jobId: string, filename: string): string {
  return `${API_BASE}/api/jobs/${jobId}/outputs/${filename}`;
}

export async function healthCheck(): Promise<{ status: string; version: string }> {
  return request("/health");
}
