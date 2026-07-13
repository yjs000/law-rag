import { describe, expect, it } from "vitest";
import { renderCsv, renderMarkdown } from "./checklist-export";

const input = {
  question: '허가, "신고"를 확인해줘',
  asOfDate: "2026-07-13",
  projectStage: "인허가",
  checklist: [
    { label: "허가 대상 확인", status: "open", citation_ids: ["C1", "C2"] },
  ],
};

describe("checklist export", () => {
  it("renders Markdown as the default human-readable format", () => {
    expect(renderMarkdown(input)).toContain("- [ ] 허가 대상 확인 (C1, C2)");
    expect(renderMarkdown(input)).toContain("법령 기준일: 2026-07-13");
  });

  it("renders Excel-friendly CSV and escapes quotes", () => {
    const csv = renderCsv(input);
    expect(csv.startsWith("\uFEFF")).toBe(true);
    expect(csv).toContain('"허가, ""신고""를 확인해줘"');
    expect(csv).toContain('"C1; C2"');
  });
});
