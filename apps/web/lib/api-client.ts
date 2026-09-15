import type {
  ConversationPage,
  ConversationTurnPage,
  MockUser,
  QuestionHistoryItem,
  QuestionInput,
  QuestionResponse,
} from "./contracts";
import { createClient } from "./supabase/client";
import {
  runV2Execution,
  V2ExecutionEventError,
  V2ExecutionHttpError,
  V2ExecutionPhaseError,
  type V2ExecutionEvent,
} from "./v2-execution";
import { backendDisplayMessage } from "./backend-display-message";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const CONSENT_KEY = "law-rag-pending-consent";
export const TERMS_VERSION = "beta-2026-07-15";
export const PRIVACY_VERSION = "beta-2026-07-15";

export type ApiErrorCode = string | null;

export class ApiError extends Error {
  constructor(
    readonly publicMessage: string | null,
    readonly status: number,
    readonly code: ApiErrorCode = null,
  ) {
    super(publicMessage ?? `HTTP ${status}`);
    this.name = "ApiError";
  }
}

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

async function request<T>(path: string, init?: RequestInit, authToken?: string | null): Promise<T> {
  const authentication = authToken === undefined
    ? await authHeaders()
    : authToken
      ? { Authorization: `Bearer ${authToken}` }
      : {};
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { ...authentication, ...init?.headers },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    const message = typeof detail === "string"
      ? detail
      : typeof detail?.message === "string"
        ? detail.message
        : "요청을 처리하지 못했습니다.";
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function getStoredUser(): Promise<MockUser | null> {
  const token = await accessToken();
  if (!token) return null;
  const consent = typeof window !== "undefined"
    ? window.sessionStorage.getItem(CONSENT_KEY)
    : null;
  try {
    const user = await request<MockUser>("/v1/auth/me", {
      headers: consent ? {
        "X-Terms-Version": TERMS_VERSION,
        "X-Privacy-Version": PRIVACY_VERSION,
      } : undefined,
    }, token);
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

export async function askQuestion(
  input: QuestionInput,
  signal?: AbortSignal,
  onEvent?: (event: V2ExecutionEvent) => void,
): Promise<QuestionResponse> {
  try {
    return await runV2Execution(input, {
      fetch: (request, init) => fetch(request, init),
      apiUrl: API,
      headers: await authHeaders(),
      idempotencyKey: () => crypto.randomUUID(),
      onEvent,
    }, signal);
  } catch (error) {
    if (error instanceof V2ExecutionPhaseError && error.reasonCode === "provider_unavailable") {
      throw new ApiError(
        "AI 제공자를 일시적으로 사용할 수 없습니다. 다시 시도해 주세요.",
        503,
        "provider_unavailable",
      );
    }
    if (error instanceof V2ExecutionEventError) {
      const code: ApiErrorCode = error.reasonCode === "system_busy" ? "system_busy" : null;
      throw new ApiError(error.publicMessage, 500, code);
    }
    if (error instanceof V2ExecutionHttpError) {
      const raw = error.detail as { detail?: unknown; code?: unknown; reason_code?: unknown } | null;
      const detail = raw?.detail;
      const code: ApiErrorCode = error.detail === "system_busy"
        || raw?.code === "system_busy"
        || raw?.reason_code === "system_busy"
        || detail === "system_busy"
        || (detail as { code?: unknown } | null)?.code === "system_busy"
        ? "system_busy"
        : null;
      throw new ApiError(backendDisplayMessage(error.detail), error.status, code);
    }
    throw error;
  }
}

export function listConversations(cursor?: string | null, limit = 20): Promise<ConversationPage> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (cursor) query.set("cursor", cursor);
  return request(`/v1/conversations?${query}`);
}

export function listConversationTurns(
  conversationId: string,
  cursor?: string | null,
  limit = 20,
): Promise<ConversationTurnPage> {
  const query = new URLSearchParams({ limit: String(limit) });
  if (cursor) query.set("cursor", cursor);
  return request(`/v1/conversations/${encodeURIComponent(conversationId)}/turns?${query}`);
}

export function deleteConversation(conversationId: string): Promise<void> {
  return request(`/v1/conversations/${encodeURIComponent(conversationId)}`, { method: "DELETE" });
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
