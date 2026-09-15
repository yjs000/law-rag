import type { QuestionResponse } from "./contracts";

export function liveCoreResponse(
  requestId: string,
  data: Record<string, unknown>,
): QuestionResponse | null {
  const summary = data.summary;
  if (typeof summary !== "string" || !summary.trim()) return null;

  return {
    request_id: requestId,
    mode: "ai",
    summary,
    scope: typeof data.scope === "string" ? data.scope : "",
    sections: [],
    checklist: [],
    citations: coreCitations(data.citations),
    limitations: stringArray(data.limitations),
  };
}

function stringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function coreCitations(value: unknown): QuestionResponse["citations"] {
  if (!Array.isArray(value)) return [];
  return value.filter((citation): citation is QuestionResponse["citations"][number] => (
    typeof citation === "object" && citation !== null
    && typeof (citation as { id?: unknown }).id === "string"
    && typeof (citation as { document_title?: unknown }).document_title === "string"
    && typeof (citation as { version_label?: unknown }).version_label === "string"
    && typeof (citation as { path?: unknown }).path === "string"
    && typeof (citation as { quote?: unknown }).quote === "string"
    && typeof (citation as { source_url?: unknown }).source_url === "string"
  ));
}
