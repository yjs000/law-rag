import type {
  CorpusStatus,
  MockUser,
  QuestionHistoryItem,
  QuestionInput,
  QuestionResponse,
} from "./contracts";
import { createClient } from "./supabase/client";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const CONSENT_KEY = "law-rag-pending-consent";
export const TERMS_VERSION = "beta-2026-07-15";
export const PRIVACY_VERSION = "beta-2026-07-15";

async function accessToken(): Promise<string | null> {
  try {
    const { data } = await createClient().auth.getSession();
    return data.session?.access_token ?? null;
  } catch {
    return null;
  }
}

async function authHeaders(): Promise<HeadersInit> {
  const token = await accessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { ...(await authHeaders()), ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail ?? "요청을 처리하지 못했습니다.");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function getStoredUser(): Promise<MockUser | null> {
  if (!(await accessToken())) return null;
  const consent = typeof window !== "undefined"
    ? window.sessionStorage.getItem(CONSENT_KEY)
    : null;
  try {
    const user = await request<MockUser>("/v1/auth/me", {
      headers: consent ? {
        "X-Terms-Version": TERMS_VERSION,
        "X-Privacy-Version": PRIVACY_VERSION,
      } : undefined,
    });
    if (consent) window.sessionStorage.removeItem(CONSENT_KEY);
    return user;
  } catch (error) {
    throw error;
  }
}

export async function startGoogleAuth(view: "login" | "signup"): Promise<void> {
  if (view === "signup") window.sessionStorage.setItem(CONSENT_KEY, "accepted");
  else window.sessionStorage.removeItem(CONSENT_KEY);
  const redirectTo = `${window.location.origin}/auth/callback`;
  const { error } = await createClient().auth.signInWithOAuth({
    provider: "google",
    options: { redirectTo },
  });
  if (error) throw error;
}

export async function logout(): Promise<void> {
  const { error } = await createClient().auth.signOut();
  if (error) throw error;
}

export async function deleteAccount(): Promise<void> {
  await request<void>("/v1/account", { method: "DELETE" });
  await createClient().auth.signOut({ scope: "local" });
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
  return request(`/v1/questions/history/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function downloadPdf(historyId: string): Promise<Blob> {
  const response = await fetch(
    `${API}/v1/questions/history/${encodeURIComponent(historyId)}/checklist?format=pdf`,
    { headers: await authHeaders() },
  );
  if (!response.ok) throw new Error("PDF 출력본을 만들지 못했습니다.");
  return response.blob();
}
