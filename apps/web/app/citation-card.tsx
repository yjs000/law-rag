import { SafeText } from "./safe-text";
import type { Citation } from "../lib/contracts";

export function CitationCard({
  citation,
  htmlId,
  open,
}: {
  citation: Citation;
  htmlId: string;
  open: boolean;
}) {
  return (
    <details className={open ? "source selected" : "source"} id={htmlId} open={open}>
      <summary>
        <span>
          <strong>
            {citation.id} · <SafeText>{citation.document_title}</SafeText> <SafeText>{citation.path}</SafeText>
          </strong>
          <small><SafeText>{citation.version_label}</SafeText></small>
        </span>
      </summary>
      <blockquote><SafeText>{citation.quote}</SafeText></blockquote>
      <a href={citation.source_url} rel="noreferrer" target="_blank">
        원문 보기 ↗
      </a>
    </details>
  );
}
