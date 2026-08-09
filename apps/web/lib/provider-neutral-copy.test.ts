import { describe, expect, it } from "vitest";
import {
  accountDialogCopy,
  answerModeBadgeLabel,
} from "./provider-neutral-copy";

const providerSpecificPattern = /terra|nvidia|nemotron|gpt-?\d/i;

describe("provider-neutral user-facing copy (0036)", () => {
  it("describes an available AI account without exposing a provider or model", () => {
    const copy = accountDialogCopy(true);

    expect(copy).toEqual({ title: "계정 및 AI 설정", status: "AI 사용 가능" });
    expect(`${copy.title} ${copy.status}`).not.toMatch(providerSpecificPattern);
  });

  it("describes an unavailable AI account as search-only", () => {
    expect(accountDialogCopy(false)).toEqual({
      title: "계정 및 AI 설정",
      status: "검색 전용",
    });
  });

  it("labels AI and search-only answers without exposing a provider or model", () => {
    const aiLabel = answerModeBadgeLabel("ai");
    const searchLabel = answerModeBadgeLabel("search_only");

    expect(aiLabel).toBe("AI 답변 · 인용 검증");
    expect(searchLabel).toBe("검색 전용");
    expect(`${aiLabel} ${searchLabel}`).not.toMatch(providerSpecificPattern);
  });
});
