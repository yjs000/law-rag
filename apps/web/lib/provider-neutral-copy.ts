export const ACCOUNT_SETTINGS_TITLE = "계정 및 AI 설정";

export function answerModeBadgeLabel(mode: "ai" | "search_only"): string {
  return mode === "ai" ? "AI 답변 · 인용 검증" : "검색 전용";
}
