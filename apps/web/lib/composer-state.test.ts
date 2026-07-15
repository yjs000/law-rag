import { describe, expect, it } from "vitest";
import { consumeQuestionDraft } from "./composer-state";

describe("consumeQuestionDraft", () => {
  it("keeps the normalized submitted message and clears the next draft", () => {
    expect(consumeQuestionDraft("  전기사업 허가 요건은?  ")).toEqual({
      submittedQuestion: "전기사업 허가 요건은?",
      nextDraft: "",
    });
  });

  it("does not consume a draft that is too short", () => {
    expect(consumeQuestionDraft("  가 ")).toBeNull();
  });
});
