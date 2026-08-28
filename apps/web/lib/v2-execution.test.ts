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
    )).rejects.toThrow("알 수 없는");
  });
});
