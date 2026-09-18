export type ConsumedQuestionDraft = {
  submittedQuestion: string;
  nextDraft: "";
};

export function consumeQuestionDraft(draft: string): ConsumedQuestionDraft | null {
  const submittedQuestion = draft.trim();
  if (submittedQuestion.length === 0 || submittedQuestion.length > 2_000) return null;

  return { submittedQuestion, nextDraft: "" };
}

export function submitQuestionDraft(
  draft: string,
  onSubmit: (submission: ConsumedQuestionDraft) => void,
): boolean {
  const submission = consumeQuestionDraft(draft);
  if (!submission) return false;
  onSubmit(submission);
  return true;
}
