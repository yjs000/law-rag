import type { CorpusStatus, QuestionResponse } from "./contracts";

export type AnswerPreference = "terra" | "search_only";

export const TERRA_FALLBACK_NOTICE = "AI 생성 한도 또는 연결 문제로 검색 전용으로 전환합니다.";
export const AI_UNAVAILABLE_NOTICE = "AI 생성 한도 또는 연결 문제로 답변을 생성할 수 없습니다.";

export type AnswerModeResolution = {
  preference: AnswerPreference;
  notice: string | null;
};

export function isTerraUnavailable(
  status: Pick<CorpusStatus, "ai_available"> | null,
): boolean {
  return status?.ai_available === false;
}

export function isTerraAvailabilityFailure(
  reason: QuestionResponse["fallback_reason"],
): boolean {
  return reason === "ai_disabled"
    || reason === "quota_exhausted"
    || reason === "billing_or_quota_error";
}

export function resolveCorpusAnswerMode(
  status: Pick<CorpusStatus, "ai_available">,
  searchOnlyEnabled = true,
): AnswerModeResolution {
  if (status.ai_available) return { preference: "terra", notice: null };
  return searchOnlyEnabled
    ? { preference: "search_only", notice: TERRA_FALLBACK_NOTICE }
    : { preference: "terra", notice: AI_UNAVAILABLE_NOTICE };
}

export function resolveResponseAnswerMode(
  requested: AnswerPreference,
  response: Pick<QuestionResponse, "fallback_reason" | "mode" | "requested_answer_mode">,
  searchOnlyEnabled = true,
): AnswerModeResolution {
  if (response.mode === "ai") return { preference: "terra", notice: null };
  if (!searchOnlyEnabled) return { preference: "terra", notice: AI_UNAVAILABLE_NOTICE };
  if (requested === "search_only") return { preference: "search_only", notice: null };

  const terraWasRequested = response.requested_answer_mode === "terra"
    || (response.requested_answer_mode === undefined && requested === "terra");
  const notice = terraWasRequested || response.fallback_reason ? TERRA_FALLBACK_NOTICE : null;

  return isTerraAvailabilityFailure(response.fallback_reason)
    ? { preference: "search_only", notice }
    : { preference: "terra", notice };
}
