import { describe, expect, it } from "vitest";

import { SUGGESTED_QUESTIONS } from "./suggested-questions";

describe("SUGGESTED_QUESTIONS", () => {
  it("uses natural questions backed by the retrieval evaluation set", () => {
    expect(SUGGESTED_QUESTIONS).toEqual([
      "전기저장시설을 설치할 때 적용되는 화재안전 기준은 무엇인가요?",
      "전기사업 허가를 신청할 때 제출해야 하는 서류는 무엇인가요?",
      "전기사업법 제7조 제1항은 어떤 허가를 규정하나요?",
    ]);
  });
});
