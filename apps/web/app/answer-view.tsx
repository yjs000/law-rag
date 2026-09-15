import type { QuestionResponse } from "../lib/contracts";
import type { ExportFormat } from "../lib/checklist-export";
import { filterCitations, type DocumentKind } from "../lib/source-filter";
import { answerModeBadgeLabel } from "../lib/provider-neutral-copy";
import { CitationCard } from "./citation-card";
import { SafeText } from "./safe-text";
export function AnswerView({
  asOf,
  documentKinds,
  exportFormat,
  exporting,
  messageId,
  onCitation,
  onExport,
  onExportFormat,
  pendingDetail,
  question,
  response,
  selectedCitationId,
}: {
  asOf: string;
  documentKinds: Set<DocumentKind>;
  exportFormat: ExportFormat;
  exporting: boolean;
  messageId: string;
  onCitation: (messageId: string, response: QuestionResponse, id: string) => void;
  onExport: (response: QuestionResponse, question: string, asOf: string) => void;
  onExportFormat: (format: ExportFormat) => void;
  pendingDetail: boolean;
  question: string;
  response: QuestionResponse;
  selectedCitationId: string | null;
}) {
  const citations = filterCitations(response.citations, documentKinds);
  return <>
      <div className="answer-meta">
        <span className={response.mode === "ai" ? "mode-badge" : "mode-badge search"}>{answerModeBadgeLabel(response.mode)}</span>
        <span>기준일 {asOf}</span>
      </div>
      <p className="summary"><SafeText>{response.summary}</SafeText></p>
      {citations.length > 0 && (
        <section className="sources">
          <h2>원문 근거 <span>{citations.length}건</span></h2>
          {citations.map((citation) => <CitationCard
            citation={citation}
            htmlId={`citation-${messageId}-${citation.id}`}
            key={citation.id}
            open={selectedCitationId === `${messageId}:${citation.id}`}
          />)}
        </section>
      )}
      {(response.scope || response.limitations.length > 0) && (
        <section className="limitations">
          <h2>범위와 한계</h2>
          {response.scope && <p><SafeText>{response.scope}</SafeText></p>}
          {response.limitations.map((item, index) => <p key={`${item}-${index}`}>· <SafeText>{item}</SafeText></p>)}
        </section>
      )}
      {pendingDetail && <p aria-label="상세 답변 생성 중" className="detail-progress">…</p>}
      {response.sections.map((section, index) => (
        <section className="claim" key={`${section.claim}-${index}`}>
          <h2><SafeText>{section.claim}</SafeText></h2>
          <p><SafeText>{section.explanation}</SafeText></p>
          <div className="citation-links">
            {section.citation_ids.map((id) => <button
                className={selectedCitationId === `${messageId}:${id}` ? "selected" : ""}
                key={id}
                onClick={() => onCitation(messageId, response, id)}
              >
                {id} 원문
              </button>)}
          </div>
        </section>
      ))}
      {response.checklist.length > 0 && (
        <section className="checklist">
          <div className="section-title-row">
            <h2>확인 체크리스트</h2>
            <div className="export-controls">
              <select aria-label="내보내기 형식" value={exportFormat} onChange={(event) => onExportFormat(event.target.value as ExportFormat)}>
                <option value="md">Markdown</option>
                <option value="csv">CSV</option>
                <option value="pdf">PDF</option>
              </select>
              <button disabled={exporting} onClick={() => onExport(response, question, asOf)}>{exporting ? "생성 중" : "내보내기"}</button>
            </div>
          </div>
          {response.checklist.map((item, index) => (
            <div className="check-item" key={`${item.label}-${index}`}>
              <span aria-hidden="true">□</span>
              <p>
                <SafeText>{item.label}</SafeText>
                {item.citation_ids.map((id) => <button className="inline-cite" key={id} onClick={() => onCitation(messageId, response, id)}>{id}</button>)}
              </p>
            </div>
          ))}
        </section>
      )}
    </>;
}
