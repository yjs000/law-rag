import { describe, expect, it } from "vitest";

import { runV2Execution } from "./v2-execution";

const response = { mode: "search_only", summary: "근거 답변", scope: "", sections: [], checklist: [], citations: [], limitations: [] };

describe("runV2Execution", () => {
  it("follows prepare to core to finalize and trusts only complete.response", async () => {
    const calls: string[] = [];
    const fetch = async (url: string) => {
      calls.push(url);
      if (url.endsWith("/v2/question-executions")) return Response.json({ execution_id: "exec-1", next_action: "generate_core" });
      if (url.endsWith("/core")) return new Response('event: phase_complete\ndata: {"next_action":"generate_detail"}\n\n');
      return new Response(`event: complete\ndata: {"response":${JSON.stringify(response)}}\n\n`);
    };

    await expect(runV2Execution(
      { question: "질문", as_of_date: "2026-08-28", project_stage: "planning" },
      { fetch: fetch as typeof globalThis.fetch, apiUrl: "http://api", headers: {}, idempotencyKey: () => "key" },
    )).resolves.toEqual(response);
    expect(calls).toEqual([
      "http://api/v2/question-executions",
      "http://api/v2/question-executions/exec-1/core",
      "http://api/v2/question-executions/exec-1/finalize",
    ]);
  });

  it("stops on an unknown next action", async () => {
    const fetch = async () => Response.json({ execution_id: "exec-1", next_action: "invented" });
    await expect(runV2Execution(
      { question: "질문", as_of_date: "2026-08-28", project_stage: "planning" },
      { fetch: fetch as typeof globalThis.fetch, apiUrl: "http://api", headers: {}, idempotencyKey: () => "key" },
    )).rejects.toThrow("준비 응답");
  });

  it("reconnects one interrupted phase without creating a second execution", async () => {
    let coreAttempts = 0;
    const fetch = async (url: string) => {
      if (url.endsWith("/v2/question-executions")) return Response.json({ execution_id: "exec-1", next_action: "generate_core" });
      if (url.endsWith("/core")) {
        coreAttempts += 1;
        if (coreAttempts === 1) throw new TypeError("network interrupted");
        return new Response(`event: complete\ndata: {"response":${JSON.stringify(response)}}\n\n`);
      }
      throw new Error("unexpected finalize");
    };

    await expect(runV2Execution(
      { question: "질문", as_of_date: "2026-08-28", project_stage: "planning" },
      { fetch: fetch as typeof globalThis.fetch, apiUrl: "http://api", headers: {}, idempotencyKey: () => "key" },
    )).resolves.toEqual(response);
    expect(coreAttempts).toBe(2);
  });

  it("incrementally parses split frames and bounds a live-phase reconnect", async () => {
    let coreAttempts = 0;
    const fetch = async (url: string, init?: RequestInit) => {
      if (url.endsWith("/v2/question-executions")) {
        return Response.json({
          execution_id: "exec-1",
          next_action: "generate_core",
          execution_capability: "capability-1",
        });
      }
      if (url.endsWith("/core")) {
        coreAttempts += 1;
        expect(new Headers(init?.headers).get("X-Execution-Capability")).toBe("capability-1");
        if (coreAttempts === 1) return new Response('event: summary\ndata: {"summary":"부분"}\n\n');
        return streamed(["event: phase_", 'complete\ndata: {"next_action":"generate_detail"}\n\n']);
      }
      return streamed([`event: complete\ndata: {"response":${JSON.stringify(response)}}\n\n`]);
    };

    await expect(runV2Execution(
      { question: "질문", as_of_date: "2026-08-28", project_stage: "planning" },
      {
        fetch: fetch as typeof globalThis.fetch,
        apiUrl: "http://api",
        headers: {},
        idempotencyKey: () => "key",
        reconnectDelayMs: () => 0,
      },
    )).resolves.toEqual(response);
    expect(coreAttempts).toBe(2);
  });

  it("cancels the issued v2 execution when the caller aborts", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    const controller = new AbortController();
    let coreStarted!: () => void;
    const coreStartedPromise = new Promise<void>((resolve) => { coreStarted = resolve; });
    const fetch = (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/v2/question-executions")) {
        return Promise.resolve(Response.json({
          execution_id: "exec-1",
          next_action: "generate_core",
          execution_capability: "capability-1",
        }));
      }
      if (url.endsWith("/core")) {
        coreStarted();
        return new Promise<Response>((_resolve, reject) => {
          init?.signal?.addEventListener("abort", () => {
            reject(new DOMException("Aborted", "AbortError"));
          });
        });
      }
      return Promise.resolve(new Response(null, { status: 202 }));
    };

    const running = runV2Execution(
      { question: "질문", as_of_date: "2026-08-28", project_stage: "planning" },
      { fetch: fetch as typeof globalThis.fetch, apiUrl: "http://api", headers: {}, idempotencyKey: () => "key" },
      controller.signal,
    );
    await coreStartedPromise;
    controller.abort();

    await expect(running).rejects.toMatchObject({ name: "AbortError" });
    const cancellation = calls.find(({ url, init }) => url.endsWith("/exec-1") && init?.method === "DELETE");
    expect(new Headers(cancellation?.init?.headers).get("X-Execution-Capability")).toBe("capability-1");
  });
});

function streamed(chunks: string[]): Response {
  const encoder = new TextEncoder();
  return new Response(new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  }));
}
