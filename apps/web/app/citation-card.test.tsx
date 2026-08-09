import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { CitationCard } from "./citation-card";
import type { Citation } from "../lib/contracts";

const citation: Citation = {
  id: "C1",
  document_title: "전기사업법",
  version_label: "MST 1",
  path: "제7조제1항",
  quote: "전기사업을 하려는 자는 산업통상자원부장관의 허가를 받아야 한다.",
  source_url: "https://www.law.go.kr/법령/전기사업법",
};

describe("CitationCard", () => {
  it("renders only the header inside <summary>, keeping quote and source link outside it", () => {
    const html = renderToStaticMarkup(<CitationCard citation={citation} htmlId="citation-1-C1" open={false} />);
    const summaryEnd = html.indexOf("</summary>");
    const summaryHtml = html.slice(0, summaryEnd);
    expect(summaryHtml).toContain("전기사업법");
    expect(summaryHtml).toContain("제7조제1항");
    expect(summaryHtml).not.toContain("산업통상자원부장관의 허가");
    expect(summaryHtml).not.toContain("law.go.kr");
  });

  it("renders a link to source_url after the quote", () => {
    const html = renderToStaticMarkup(<CitationCard citation={citation} htmlId="citation-1-C1" open={false} />);
    const quoteIndex = html.indexOf("산업통상자원부장관의 허가");
    const linkIndex = html.indexOf(`href="${citation.source_url}"`);
    expect(linkIndex).toBeGreaterThan(-1);
    expect(linkIndex).toBeGreaterThan(quoteIndex);
  });

  it("opens external links safely", () => {
    const html = renderToStaticMarkup(<CitationCard citation={citation} htmlId="citation-1-C1" open={false} />);
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noreferrer"');
  });

  it("marks the card open and selected when the caller says so", () => {
    const html = renderToStaticMarkup(<CitationCard citation={citation} htmlId="citation-1-C1" open={true} />);
    expect(html).toContain('class="source selected"');
    expect(html).toContain("open=\"\"");
  });
});
