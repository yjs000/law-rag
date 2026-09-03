import { describe, expect, it } from "vitest";
import { resolveResponseAnswerMode } from "./answer-mode";

describe("search-only feature flag", () => {
  it("keeps Terra selected instead of falling back when search-only is disabled", () => {
    const expected = {
      preference: "terra",
      notice: "AI 생성 한도 또는 연결 문제로 답변을 생성할 수 없습니다.",
    };
    expect(resolveResponseAnswerMode("terra", {
      mode: "search_only",
      requested_answer_mode: "terra",
      fallback_reason: "quota_exhausted",
    }, false)).toEqual(expected);
  });
});
