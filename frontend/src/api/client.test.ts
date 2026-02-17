import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  ApiError,
  createJob,
  listJobs,
  getJob,
  deleteJob,
  listOutputs,
  getOutputUrl,
  healthCheck,
} from "./client";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function jsonResponse(data: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? "OK" : "Error",
    json: () => Promise.resolve(data),
  };
}

beforeEach(() => {
  mockFetch.mockReset();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ApiError", () => {
  it("stores status and message", () => {
    const err = new ApiError(404, "Not found");
    expect(err.status).toBe(404);
    expect(err.message).toBe("Not found");
    expect(err.name).toBe("ApiError");
    expect(err).toBeInstanceOf(Error);
  });
});

describe("getOutputUrl", () => {
  it("builds the correct download URL", () => {
    const url = getOutputUrl("abc-123", "model.ply");
    expect(url).toBe("http://localhost:8000/api/jobs/abc-123/outputs/model.ply");
  });
});

describe("healthCheck", () => {
  it("returns health data on success", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ status: "healthy", version: "1.0.0" }),
    );
    const result = await healthCheck();
    expect(result).toEqual({ status: "healthy", version: "1.0.0" });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/health",
      undefined,
    );
  });

  it("throws ApiError on failure", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ detail: "Service unavailable" }, 503),
    );
    await expect(healthCheck()).rejects.toThrow(ApiError);

    mockFetch.mockResolvedValueOnce(
      jsonResponse({ detail: "Service unavailable" }, 503),
    );
    await expect(healthCheck()).rejects.toThrow("Service unavailable");
  });
});

describe("listJobs", () => {
  it("fetches jobs with default params", async () => {
    const data = { jobs: [], total: 0 };
    mockFetch.mockResolvedValueOnce(jsonResponse(data));

    const result = await listJobs();
    expect(result).toEqual(data);

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("/api/jobs?");
    expect(url).toContain("limit=50");
    expect(url).toContain("offset=0");
  });

  it("passes status filter", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ jobs: [], total: 0 }));

    await listJobs("completed", 10, 5);

    const url = mockFetch.mock.calls[0][0] as string;
    expect(url).toContain("status=completed");
    expect(url).toContain("limit=10");
    expect(url).toContain("offset=5");
  });
});

describe("getJob", () => {
  it("fetches a single job", async () => {
    const job = { id: "abc-123", status: "completed", method: "splatfacto" };
    mockFetch.mockResolvedValueOnce(jsonResponse(job));

    const result = await getJob("abc-123");
    expect(result).toEqual(job);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/jobs/abc-123",
      undefined,
    );
  });

  it("throws on 404", async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse({ detail: "Job not found" }, 404),
    );
    await expect(getJob("missing")).rejects.toThrow("Job not found");
  });
});

describe("createJob", () => {
  it("sends FormData with video file", async () => {
    const job = { id: "new-job", status: "pending" };
    mockFetch.mockResolvedValueOnce(jsonResponse(job));

    const video = new File(["video-data"], "scene.mp4", { type: "video/mp4" });
    const result = await createJob({ video }, { method: "splatfacto" });

    expect(result).toEqual(job);
    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/jobs");
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);

    const form = init.body as FormData;
    expect(form.get("video")).toBeInstanceOf(File);
    expect(form.get("method")).toBe("splatfacto");
  });

  it("sends FormData with multiple images", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ id: "img-job", status: "pending" }));

    const images = [
      new File(["img1"], "frame001.jpg", { type: "image/jpeg" }),
      new File(["img2"], "frame002.jpg", { type: "image/jpeg" }),
    ];
    await createJob({ images }, { method: "nerfacto", maxIterations: 5000 });

    const form = mockFetch.mock.calls[0][1].body as FormData;
    expect(form.getAll("images")).toHaveLength(2);
    expect(form.get("method")).toBe("nerfacto");
    expect(form.get("max_iterations")).toBe("5000");
  });

  it("defaults method to splatfacto", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({ id: "x", status: "pending" }));

    const video = new File(["v"], "v.mp4");
    await createJob({ video });

    const form = mockFetch.mock.calls[0][1].body as FormData;
    expect(form.get("method")).toBe("splatfacto");
  });
});

describe("deleteJob", () => {
  it("sends DELETE request", async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse({}));

    await deleteJob("abc-123");

    const [url, init] = mockFetch.mock.calls[0];
    expect(url).toBe("http://localhost:8000/api/jobs/abc-123");
    expect(init.method).toBe("DELETE");
  });
});

describe("listOutputs", () => {
  it("fetches output files for a job", async () => {
    const outputs = [
      { name: "model.ply", path: "/out/model.ply", size_bytes: 1024, suffix: ".ply" },
    ];
    mockFetch.mockResolvedValueOnce(jsonResponse(outputs));

    const result = await listOutputs("abc-123");
    expect(result).toEqual(outputs);
    expect(mockFetch).toHaveBeenCalledWith(
      "http://localhost:8000/api/jobs/abc-123/outputs",
      undefined,
    );
  });
});

describe("error handling", () => {
  it("uses statusText when detail is missing", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 500,
      statusText: "Internal Server Error",
      json: () => Promise.resolve({}),
    });

    await expect(getJob("x")).rejects.toThrow("Internal Server Error");
  });

  it("handles non-JSON error responses", async () => {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status: 502,
      statusText: "Bad Gateway",
      json: () => Promise.reject(new Error("not json")),
    });

    await expect(getJob("x")).rejects.toThrow("Bad Gateway");
  });
});
