export type ConsumedQuestionDraft = {
  submittedQuestion: string;
  nextDraft: "";
};

export function consumeQuestionDraft(draft: string): ConsumedQuestionDraft | null {
  const submittedQuestion = draft.trim();
  if (submittedQuestion.length < 2) return null;

  return { submittedQuestion, nextDraft: "" };
}
