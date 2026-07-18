import { afterEach, describe, expect, it, vi } from "vitest";
import {
  askQuestion,
  deleteQuestionHistory,
  downloadPdf,
  getStoredUser,
  listQuestionHistory,
  startGoogleAuth,
} from "./api-client";
import type { QuestionHistoryItem, QuestionResponse } from "./contracts";

const auth = vi.hoisted(() => ({
  getSession: vi.fn(),
  signInWithOAuth: vi.fn(),
  signOut: vi.fn(),
}));

vi.mock("./supabase/client", () => ({ createClient: () => ({ auth }) }));

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
  auth.getSession.mockReset();
  auth.signInWithOAuth.mockReset();
});

describe("Supabase authenticated question workflow", () => {
  it("starts PKCE login and sends the Supabase bearer token to API calls", async () => {
    const values = new Map<string, string>();
    vi.stubGlobal("window", {
      location: { origin: "http://localhost:3000" },
      sessionStorage: {
        getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key, value),
        removeItem: (key: string) => values.delete(key),
      },
    });
    auth.getSession.mockResolvedValue({ data: { session: { access_token: "token-1" } } });
    auth.signInWithOAuth.mockResolvedValue({ error: null });
    const fetchMock = vi.fn(async (input: string | URL | Request, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/v1/auth/me")) return Response.json({ id: "user-1", email: "researcher@example.com", display_name: "법령 연구자", auth_provider: "google", created_at: "2026-07-14T00:00:00Z" });
      if (url.endsWith("/v1/questions") && init?.method === "POST") return Response.json(answer);
      if (url.endsWith("/v1/questions/history")) return Response.json([history]);
      if (url.includes("/checklist?format=pdf")) return new Response(new Uint8Array([37, 80, 68, 70]), { headers: { "Content-Type": "application/pdf" } });
      if (url.endsWith("/v1/questions/history/history-1") && init?.method === "DELETE") return new Response(null, { status: 204 });
      return new Response(null, { status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    await startGoogleAuth("signup");
    expect(auth.signInWithOAuth).toHaveBeenCalledWith({ provider: "google", options: { redirectTo: "http://localhost:3000/auth/callback" } });
    expect((await getStoredUser())?.id).toBe("user-1");
    expect(auth.getSession).toHaveBeenCalledTimes(1);
    expect((await askQuestion(history.request)).request_id).toBe("history-1");
    expect(await listQuestionHistory()).toEqual([history]);
    expect((await downloadPdf(history.id)).type).toBe("application/pdf");
    await deleteQuestionHistory(history.id);

    for (const [, init] of fetchMock.mock.calls) {
      expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer token-1");
    }
    const meHeaders = new Headers(fetchMock.mock.calls[0][1]?.headers);
    expect(meHeaders.get("X-Terms-Version")).toBe("beta-2026-07-15");
  });
});
