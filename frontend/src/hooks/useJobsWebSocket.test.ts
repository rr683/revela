import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import useJobsWebSocket from "./useJobsWebSocket";

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  url: string;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  readyState = 0; // CONNECTING

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  close() {
    this.readyState = 3; // CLOSED
    this.onclose?.();
  }

  simulateOpen() {
    this.readyState = 1; // OPEN
    this.onopen?.();
  }

  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  simulateError() {
    this.onerror?.();
  }

  static readonly OPEN = 1;
}

beforeEach(() => {
  MockWebSocket.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket);
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("useJobsWebSocket", () => {
  it("opens a WebSocket connection on mount", () => {
    const onJobUpdate = vi.fn();
    renderHook(() => useJobsWebSocket({ onJobUpdate }));

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toContain("/ws/jobs");
  });

  it("calls onConnect when socket opens", () => {
    const onJobUpdate = vi.fn();
    const onConnect = vi.fn();

    renderHook(() => useJobsWebSocket({ onJobUpdate, onConnect }));

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    expect(onConnect).toHaveBeenCalledTimes(1);
  });

  it("calls onJobUpdate with parsed job data", () => {
    const onJobUpdate = vi.fn();

    renderHook(() => useJobsWebSocket({ onJobUpdate }));

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    const jobData = { id: "test-123", status: "training" };
    act(() => {
      MockWebSocket.instances[0].simulateMessage({
        type: "job_update",
        job: jobData,
      });
    });

    expect(onJobUpdate).toHaveBeenCalledWith(jobData);
  });

  it("ignores messages without job_update type", () => {
    const onJobUpdate = vi.fn();

    renderHook(() => useJobsWebSocket({ onJobUpdate }));

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
      MockWebSocket.instances[0].simulateMessage({ type: "ping" });
    });

    expect(onJobUpdate).not.toHaveBeenCalled();
  });

  it("ignores malformed messages", () => {
    const onJobUpdate = vi.fn();

    renderHook(() => useJobsWebSocket({ onJobUpdate }));

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
      MockWebSocket.instances[0].onmessage?.({ data: "not-json" });
    });

    expect(onJobUpdate).not.toHaveBeenCalled();
  });

  it("calls onDisconnect when socket closes", () => {
    const onJobUpdate = vi.fn();
    const onDisconnect = vi.fn();

    renderHook(() => useJobsWebSocket({ onJobUpdate, onDisconnect }));

    act(() => {
      MockWebSocket.instances[0].simulateOpen();
    });

    act(() => {
      MockWebSocket.instances[0].close();
    });

    expect(onDisconnect).toHaveBeenCalledTimes(1);
  });

  it("attempts reconnection after disconnect", () => {
    const onJobUpdate = vi.fn();

    renderHook(() => useJobsWebSocket({ onJobUpdate }));

    // First connection
    expect(MockWebSocket.instances).toHaveLength(1);

    // Simulate close
    act(() => {
      MockWebSocket.instances[0].close();
    });

    // Advance past reconnect delay
    act(() => {
      vi.advanceTimersByTime(3500);
    });

    expect(MockWebSocket.instances.length).toBeGreaterThanOrEqual(2);
  });

  it("cleans up on unmount", () => {
    const onJobUpdate = vi.fn();

    const { unmount } = renderHook(() =>
      useJobsWebSocket({ onJobUpdate }),
    );

    const ws = MockWebSocket.instances[0];
    expect(ws).toBeDefined();

    unmount();

    expect(ws.readyState).toBe(3); // CLOSED
  });
});
