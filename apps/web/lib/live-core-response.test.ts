import { describe, expect, it } from "vitest";
import type { Citation } from "./contracts";
import { liveCoreResponse } from "./live-core-response";

const citation: Citation = {
  id: "law-1",
  document_title: "전기사업법",
  version_label: "2026-01-01 시행",
  path: "제7조 제1항",
  quote: "허가를 받아야 한다.",
  source_url: "https://law.example/1",
};

describe("liveCoreResponse", () => {
  it("preserves backend fields and uses empty structural defaults", () => {
    expect(liveCoreResponse("request-1", {
      summary: "백엔드 요약 원문",
      citations: [citation],
      scope: "백엔드 범위 원문",
      limitations: ["백엔드 한계 원문"],
    })).toEqual({
      request_id: "request-1",
      mode: "ai",
      summary: "백엔드 요약 원문",
      citations: [citation],
      scope: "백엔드 범위 원문",
      limitations: ["백엔드 한계 원문"],
      sections: [],
      checklist: [],
    });
    expect(liveCoreResponse("request-1", { summary: "  원문  " })?.summary).toBe("  원문  ");
  });

  it("supports old events without scope or limitations without synthesizing copy", () => {
    expect(liveCoreResponse("request-2", {
      summary: "구버전 요약 원문",
      citations: [],
    })).toMatchObject({
      summary: "구버전 요약 원문",
      scope: "",
      limitations: [],
      sections: [],
      checklist: [],
    });
  });

  it("keeps valid citations and filters malformed citations", () => {
    expect(liveCoreResponse("request-3", {
      summary: "요약",
      citations: [citation, { ...citation, quote: 42 }, null, "invalid"],
      limitations: ["한계", 42, null],
    })).toMatchObject({ citations: [citation], limitations: ["한계"] });
  });

  it("returns null for missing or blank summaries", () => {
    expect(liveCoreResponse("request-4", { citations: [] })).toBeNull();
    expect(liveCoreResponse("request-5", { summary: "   ", citations: [] })).toBeNull();
  });
});
