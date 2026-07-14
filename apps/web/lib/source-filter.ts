import type { Citation } from "./contracts";

export type DocumentKind = "law" | "decree" | "rule" | "administrative_rule";

export const DOCUMENT_KIND_LABELS: Record<DocumentKind, string> = {
  law: "법률",
  decree: "시행령",
  rule: "시행규칙",
  administrative_rule: "행정규칙",
};

export function citationDocumentKind(citation: Citation): DocumentKind {
  if (citation.source_kind === "administrative_rule") return "administrative_rule";
  if (citation.document_title.includes("시행규칙")) return "rule";
  if (citation.document_title.includes("시행령")) return "decree";
  if (citation.source_kind === "rule" || citation.source_kind === "decree") return citation.source_kind;
  if (/고시|규정|기준|NFPC|NFTC/.test(citation.document_title)) return "administrative_rule";
  return "law";
}

export function filterCitations(
  citations: Citation[],
  enabledKinds: ReadonlySet<DocumentKind>,
): Citation[] {
  return citations.filter((citation) => enabledKinds.has(citationDocumentKind(citation)));
}
