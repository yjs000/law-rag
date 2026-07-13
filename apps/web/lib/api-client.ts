import type {
  CorpusStatus,
  MockUser,
  QuestionHistoryItem,
  QuestionInput,
  QuestionResponse,
} from "./contracts";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SESSION_KEY = "law-rag-mock-session";

type SessionEnvelope = { access_token: string; user: MockUser };

function readSession(): SessionEnvelope | null {
  if (typeof window === "undefined") return null;
  const value = window.localStorage.getItem(SESSION_KEY);
  if (!value) return null;
  try {
    return JSON.parse(value) as SessionEnvelope;
  } catch {
    window.localStorage.removeItem(SESSION_KEY);
    return null;
  }
}

function authHeaders(): HeadersInit {
  const session = readSession();
  return session ? { Authorization: `Bearer ${session.access_token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "요청을 처리하지 못했습니다.");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export function getStoredUser(): MockUser | null {
  return readSession()?.user ?? null;
}

export async function mockGoogleLogin(): Promise<MockUser> {
  const session = await request<SessionEnvelope>("/v1/auth/mock/google", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: "researcher@example.com", display_name: "법령 연구자" }),
  });
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  return session.user;
}

export async function logout(): Promise<void> {
  try {
    await request<void>("/v1/auth/logout", { method: "POST" });
  } finally {
    window.localStorage.removeItem(SESSION_KEY);
  }
}

export async function deleteAccount(): Promise<void> {
  await request<void>("/v1/account", { method: "DELETE" });
  window.localStorage.removeItem(SESSION_KEY);
}

export function getCorpusStatus(): Promise<CorpusStatus> {
  return request("/v1/corpus/status");
}

export function askQuestion(input: QuestionInput): Promise<QuestionResponse> {
  return request("/v1/questions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function listQuestionHistory(): Promise<QuestionHistoryItem[]> {
  return request("/v1/questions/history");
}

export function getQuestionHistory(id: string): Promise<QuestionHistoryItem> {
  return request(`/v1/questions/history/${encodeURIComponent(id)}`);
}

export function deleteQuestionHistory(id: string): Promise<void> {
  return request(`/v1/questions/history/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

export async function downloadPdf(historyId: string): Promise<Blob> {
  const response = await fetch(
    `${API}/v1/questions/history/${encodeURIComponent(historyId)}/checklist?format=pdf`,
    { headers: authHeaders() },
  );
  if (!response.ok) throw new Error("PDF 출력본을 만들지 못했습니다.");
  return response.blob();
}
