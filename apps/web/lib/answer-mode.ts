import type { CorpusStatus, QuestionResponse } from "./contracts";

export type AnswerPreference = "terra" | "search_only";

export const TERRA_FALLBACK_NOTICE = "AI 생성 한도 또는 연결 문제로 검색 전용으로 전환합니다.";

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
): AnswerModeResolution {
  return status.ai_available
    ? { preference: "terra", notice: null }
    : { preference: "search_only", notice: TERRA_FALLBACK_NOTICE };
}

export function resolveResponseAnswerMode(
  requested: AnswerPreference,
  response: Pick<QuestionResponse, "fallback_reason" | "mode" | "requested_answer_mode">,
): AnswerModeResolution {
  if (response.mode === "ai") return { preference: "terra", notice: null };

  const terraWasRequested = response.requested_answer_mode === "terra"
    || (response.requested_answer_mode === undefined && requested === "terra");
  return {
    preference: "search_only",
    notice: terraWasRequested || response.fallback_reason ? TERRA_FALLBACK_NOTICE : null,
  };
}
