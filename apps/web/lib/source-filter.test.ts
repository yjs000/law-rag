import { describe, expect, it } from "vitest";
import { citationDocumentKind, filterCitations } from "./source-filter";
import type { Citation } from "./contracts";

const citation = (document_title: string): Citation => ({
  id: document_title,
  document_title,
  version_label: "현행",
  path: "제1조",
  quote: "원문",
  source_url: "https://law.go.kr",
});

describe("source filters", () => {
  it("classifies specific subordinate kinds before broad rules", () => {
    expect(citationDocumentKind(citation("전기사업법 시행규칙"))).toBe("rule");
    expect(citationDocumentKind(citation("전기사업법 시행령"))).toBe("decree");
    expect(citationDocumentKind(citation("전기저장시설의 화재안전기술기준"))).toBe("administrative_rule");
    expect(citationDocumentKind(citation("전기사업법"))).toBe("law");
    expect(citationDocumentKind({ ...citation("전기사업법 시행령"), source_kind: "law" })).toBe("decree");
  });

  it("filters only the source panel without altering the answer", () => {
    const citations = [citation("전기사업법"), citation("전기사업법 시행령")];
    expect(filterCitations(citations, new Set(["decree"]))).toEqual([citations[1]]);
  });
});
