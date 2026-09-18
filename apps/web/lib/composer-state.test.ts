import { describe, expect, it, vi } from "vitest";
import { consumeQuestionDraft, submitQuestionDraft } from "./composer-state";

describe("consumeQuestionDraft", () => {
  it("keeps the normalized submitted message and clears the next draft", () => {
    expect(consumeQuestionDraft("  전기사업 허가 요건은?  ")).toEqual({
      submittedQuestion: "전기사업 허가 요건은?",
      nextDraft: "",
    });
  });

  it.each(["가", "1", "?", "🧭"])("consumes a non-whitespace one-character draft: %s", (question) => {
    expect(consumeQuestionDraft(` ${question} `)).toEqual({
      submittedQuestion: question,
      nextDraft: "",
    });
  });

  it.each(["", " ", "\t", "\n", " \t\n "])("does not consume a whitespace-only draft: %j", (question) => {
    expect(consumeQuestionDraft(question)).toBeNull();
  });

  it("accepts the 2,000-character question limit", () => {
    expect(consumeQuestionDraft("가".repeat(2_000))).not.toBeNull();
  });

  it("rejects a question longer than 2,000 characters", () => {
    expect(consumeQuestionDraft("가".repeat(2_001))).toBeNull();
  });

  it("does not start a fetch when submitting a whitespace-only draft", () => {
    const fetchMock = vi.fn();

    submitQuestionDraft(" \t\n ", ({ submittedQuestion }) => {
      fetchMock("/v2/question-executions", { body: JSON.stringify({ question: submittedQuestion }) });
    });

    expect(fetchMock).not.toHaveBeenCalled();
  });
});
