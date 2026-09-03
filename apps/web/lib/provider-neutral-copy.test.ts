import { describe, expect, it } from "vitest";
import { answerModeBadgeLabel } from "./provider-neutral-copy";

const providerSpecificPattern = /terra|nvidia|nemotron|gpt-?\d/i;

describe("provider-neutral user-facing copy (0036)", () => {
  it("labels AI and search-only answers without exposing a provider or model", () => {
    const aiLabel = answerModeBadgeLabel("ai");
    const searchLabel = answerModeBadgeLabel("search_only");

    expect(aiLabel).toBe("AI 답변 · 인용 검증");
    expect(searchLabel).toBe("검색 전용");
    expect(`${aiLabel} ${searchLabel}`).not.toMatch(providerSpecificPattern);
  });
});
