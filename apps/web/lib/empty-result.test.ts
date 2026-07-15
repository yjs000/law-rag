import { describe, expect, it } from "vitest";
import type { QuestionResponse } from "./contracts";
import { getEmptyResultMessage } from "./empty-result";

function response(overrides: Partial<QuestionResponse> = {}): QuestionResponse {
  return {
    mode: "search_only",
    summary: "검색 결과가 없습니다.",
    scope: "MVP 허용 목록",
    sections: [],
    checklist: [],
    citations: [],
    limitations: ["질문을 뒷받침할 근거를 찾지 못했습니다."],
    ...overrides,
  };
}

describe("empty search result messaging", () => {
  it("does not claim that a missing law name prevented an all-corpus search", () => {
    expect(getEmptyResultMessage(response({
      result_status: "no_results",
      no_results_reason: "no_matching_evidence",
    }), "1조2항은?")).toEqual({
      title: "검색 결과가 없습니다",
      reason: "기준일에 유효한 MVP 법령 범위에서 질문과 일치하는 조문을 찾지 못했습니다.",
      guidance: "법령명과 조문 번호를 함께 적어 주세요. 예: 전기사업법 제1조 제2항은?",
    });
  });

  it("maps a requested path failure code to a user-facing reason", () => {
    expect(getEmptyResultMessage(response({
      result_status: "no_results",
      no_results_reason: "requested_path_not_found",
    }), "전기사업법 제999조는?")?.reason)
      .toBe("요청한 조·항 경로를 기준일에 유효한 MVP 대상 법령에서 찾지 못했습니다.");
  });

  it("uses the same path-absent cause for a bare provision reference", () => {
    expect(getEmptyResultMessage(response({
      result_status: "no_results",
      no_results_reason: "requested_path_not_found",
    }), "999조2항은?")?.reason)
      .toBe("요청한 조·항 경로를 기준일에 유효한 MVP 대상 법령에서 찾지 못했습니다.");
  });

  it("maps a no-evidence code without exposing the internal code", () => {
    expect(getEmptyResultMessage(response({
      result_status: "no_results",
      no_results_reason: "no_matching_evidence",
    }), "저장시설 의무는?")?.reason)
      .toBe("기준일에 유효한 MVP 법령 범위에서 질문과 일치하는 조문을 찾지 못했습니다.");
  });

  it("supports an older response without result_status", () => {
    expect(getEmptyResultMessage(response(), "저장시설 의무는?")?.reason)
      .toBe("기준일에 유효한 MVP 법령 범위에서 질문과 일치하는 조문을 찾지 못했습니다.");
  });

  it("does not show an empty state when the API explicitly reports results", () => {
    expect(getEmptyResultMessage(response({ result_status: "results" }), "1조2항은?")).toBeNull();
  });

  it("does not mistake a response with citations for an empty result", () => {
    expect(getEmptyResultMessage(response({
      citations: [{
        id: "C1",
        document_title: "전기사업법",
        version_label: "현행",
        path: "제1조",
        quote: "목적",
        source_url: "https://example.test",
      }],
    }), "전기사업법 제1조는?")).toBeNull();
  });
});
