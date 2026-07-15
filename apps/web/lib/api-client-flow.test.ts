import { afterEach, describe, expect, it, vi } from "vitest";
import {
  askQuestion,
  deleteQuestionHistory,
  downloadPdf,
  getStoredUser,
  listQuestionHistory,
  mockGoogleLogin,
} from "./api-client";
import type { QuestionHistoryItem, QuestionResponse } from "./contracts";

const answer: QuestionResponse = {
  request_id: "history-1",
  mode: "search_only",
  summary: "검색 결과",
  scope: "현행 법령",
  sections: [],
  checklist: [{ label: "허가 확인", status: "open", citation_ids: ["C1"] }],
  citations: [],
  limitations: ["법률 자문을 대체하지 않습니다."],
};

const history: QuestionHistoryItem = {
  id: "history-1",
  user_id: "user-1",
  request: { question: "허가를 확인해줘", as_of_date: "2026-07-14", project_stage: "permitting", answer_mode: "terra" },
  response: answer,
  created_at: "2026-07-14T00:00:00Z",
  expires_at: "2027-07-14T00:00:00Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("mock authenticated question workflow", () => {
  it("logs in, asks, lists history, exports PDF, and deletes with the bearer session", async () => {
    const values = new Map<string, string>();
    vi.stubGlobal("window", {
      localStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
        removeItem: (key: string) => values.delete(key),
      },
    });
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/v1/auth/mock/google")) return Response.json({ access_token: "token-1", user: { id: "user-1", email: "researcher@example.com", display_name: "법령 연구자", auth_provider: "google", created_at: "2026-07-14T00:00:00Z" } });
      if (url.endsWith("/v1/questions") && init?.method === "POST") return Response.json(answer);
      if (url.endsWith("/v1/questions/history")) return Response.json([history]);
      if (url.includes("/checklist?format=pdf")) return new Response(new Uint8Array([37, 80, 68, 70]), { headers: { "Content-Type": "application/pdf" } });
      if (url.endsWith("/v1/questions/history/history-1") && init?.method === "DELETE") return new Response(null, { status: 204 });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    const user = await mockGoogleLogin();
    expect(user.auth_provider).toBe("google");
    expect(getStoredUser()?.id).toBe("user-1");
    expect((await askQuestion(history.request)).request_id).toBe("history-1");
    expect(await listQuestionHistory()).toEqual([history]);
    expect((await downloadPdf(history.id)).type).toBe("application/pdf");
    await deleteQuestionHistory(history.id);

    for (const [, init] of fetchMock.mock.calls.slice(1)) {
      expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer token-1");
    }
  });
});
