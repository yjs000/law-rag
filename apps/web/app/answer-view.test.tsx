import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AnswerView } from "./answer-view";
import type { DocumentKind } from "../lib/source-filter";
import type { QuestionResponse } from "../lib/contracts";

const citation = {
  id: "C1",
  document_title: "원자력안전법",
  version_label: "2026-09-15 현행",
  path: "제1조",
  quote: "백엔드 인용 원문",
  source_url: "https://www.law.go.kr/법령/원자력안전법",
};

const baseResponse: QuestionResponse = {
  mode: "ai",
  summary: "백엔드 요약",
  scope: "백엔드 범위",
  sections: [],
  checklist: [],
  citations: [citation],
  limitations: ["백엔드 한계"],
};

const requiredProps = {
  asOf: "2026-09-15",
  documentKinds: new Set<DocumentKind>(["law", "decree", "rule", "administrative_rule"]),
  messageId: "message-1",
  onCitation: vi.fn(),
  selectedCitationId: null,
};

describe("AnswerView", () => {
  it("passes through a no-results summary and renders core fields in order", () => {
    const html = renderToStaticMarkup(<AnswerView
      {...requiredProps}
      response={{
        ...baseResponse,
        result_status: "no_results",
        summary: "정확한 절차를 확인하려면 추가 정보가 필요합니다.",
        scope: "질문에 답하려면 추가 정보가 필요합니다.",
        limitations: ["이 서비스는 법률 자문을 대체하지 않습니다."],
      }}
    />);

    expect(html).toContain("정확한 절차를 확인하려면 추가 정보가 필요합니다.");
    expect(html).toContain("질문에 답하려면 추가 정보가 필요합니다.");
    expect(html).not.toContain("clarification_required");
    expect(html).not.toContain("라우팅:");
    expect(html).not.toContain("(검색 미실행)");
    expect(html).toContain("이 서비스는 법률 자문을 대체하지 않습니다.");
    expect(html).not.toContain("기준일에 유효한 MVP 법령 범위");
    expect(html.startsWith('<p class="summary">')).toBe(true);
    expect(html.indexOf("summary")).toBeLessThan(html.indexOf("sources"));
    expect(html.indexOf("sources")).toBeLessThan(html.indexOf("limitations"));
    expect(html).not.toContain('class="detail-progress"');
    expect(html.indexOf("summary")).toBeLessThan(html.indexOf("answer-meta"));
  });

  it("renders finalized sections and checklist after core fields without progress ellipsis", () => {
    const html = renderToStaticMarkup(<AnswerView
      {...requiredProps}
      response={{
        ...baseResponse,
        summary: "최종 백엔드 요약",
        scope: "최종 백엔드 범위",
        limitations: ["최종 백엔드 한계"],
        sections: [{ claim: "백엔드 주장", explanation: "백엔드 설명", citation_ids: ["C1"] }],
        checklist: [{ label: "백엔드 확인 항목", status: "open", citation_ids: ["C1"] }],
      }}
    />);

    expect(html).toContain("최종 백엔드 요약");
    expect(html).toContain("백엔드 주장");
    expect(html).toContain("백엔드 확인 항목");
    expect(html).toContain("C1 원문");
    expect(html).not.toContain('class="detail-progress"');
    expect(html).not.toContain("내보내기");
    expect(html).not.toContain("export-controls");
    expect(html.indexOf("limitations")).toBeLessThan(html.indexOf("백엔드 주장"));
    expect(html.indexOf("백엔드 주장")).toBeLessThan(html.indexOf("확인 체크리스트"));
    expect(html.indexOf("백엔드 요약")).toBeLessThan(html.indexOf("answer-meta"));
    expect(html.indexOf("확인 체크리스트")).toBeLessThan(html.indexOf("answer-meta"));
  });

  it("keeps selected citations and SafeText escaping", () => {
    const html = renderToStaticMarkup(<AnswerView
      {...requiredProps}
      selectedCitationId="message-1:C1"
      response={{ ...baseResponse, summary: "<script>백엔드</script>" }}
    />);

    expect(html).toContain("&lt;script&gt;백엔드&lt;/script&gt;");
    expect(html).toContain('class="source selected"');
  });
});
