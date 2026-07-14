"use client";

import { FormEvent, useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import {
  askQuestion,
  deleteAccount,
  deleteQuestionHistory,
  downloadPdf,
  getCorpusStatus,
  getQuestionHistory,
  getStoredUser,
  listQuestionHistory,
  logout,
  mockGoogleLogin,
} from "../lib/api-client";
import {
  downloadBlob,
  downloadText,
  type ExportFormat,
  renderCsv,
  renderMarkdown,
} from "../lib/checklist-export";
import { claimAnonymousLoginPrompt } from "../lib/anonymous-prompt";
import { dialogKeyAction, focusInitial, restoreFocus } from "../lib/dialog-focus";
import {
  citationDocumentKind,
  DOCUMENT_KIND_LABELS,
  filterCitations,
  type DocumentKind,
} from "../lib/source-filter";
import { SafeText } from "./safe-text";
import type {
  CorpusStatus,
  MockUser,
  QuestionHistoryItem,
  QuestionResponse,
} from "../lib/contracts";

const STAGE_LABELS: Record<string, string> = {
  planning: "기획",
  permitting: "인허가",
  construction: "시공",
  operation: "운영",
  change: "변경",
};

function LoginPrompt({
  onClose,
  onLogin,
  returnFocus,
}: {
  onClose: () => void;
  onLogin: () => void;
  returnFocus: RefObject<HTMLButtonElement | null>;
}) {
  const loginButton = useRef<HTMLButtonElement>(null);
  const dialog = useRef<HTMLElement>(null);

  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const focusReturnTarget = returnFocus.current ?? previous;
    focusInitial(loginButton.current);
    const onKeyDown = (event: KeyboardEvent) => {
      const controls = [...(dialog.current?.querySelectorAll<HTMLElement>("button, [href]") ?? [])];
      const action = dialogKeyAction({
        key: event.key,
        shiftKey: event.shiftKey,
        activeIndex: controls.indexOf(document.activeElement as HTMLElement),
        controlCount: controls.length,
      });
      if (action.type === "close") onClose();
      if (action.type === "focus") {
        event.preventDefault();
        controls[action.index]?.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      restoreFocus(focusReturnTarget);
    };
  }, [onClose, returnFocus]);

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        aria-describedby="login-prompt-description"
        aria-labelledby="login-prompt-title"
        aria-modal="true"
        className="modal"
        onMouseDown={(event) => event.stopPropagation()}
        role="dialog"
        ref={dialog}
      >
        <button aria-label="닫기" className="modal-close" onClick={onClose}>×</button>
        <div className="eyebrow">질문 이력</div>
        <h2 id="login-prompt-title">질문 기록을 남기려면 로그인하세요</h2>
        <p id="login-prompt-description">
          로그인 전 질문은 저장되지 않으며 로그인 후에도 소급 저장되지 않습니다. 팝업을 닫아도 계속 질문할 수 있습니다.
        </p>
        <button className="google-login" onClick={onLogin} ref={loginButton}>
          <span aria-hidden="true">G</span> Google로 로그인
        </button>
      </section>
    </div>
  );
}

export default function Home() {
  const [question, setQuestion] = useState("분산에너지 사업을 시작할 때 어떤 허가와 신고를 먼저 확인해야 하나요?");
  const [stage, setStage] = useState("planning");
  const [asOf, setAsOf] = useState(new Date().toISOString().slice(0, 10));
  const [result, setResult] = useState<QuestionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [corpus, setCorpus] = useState<CorpusStatus | null>(null);
  const [user, setUser] = useState<MockUser | null>(null);
  const [history, setHistory] = useState<QuestionHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [showLoginPrompt, setShowLoginPrompt] = useState(false);
  const [exportFormat, setExportFormat] = useState<ExportFormat>("md");
  const [exporting, setExporting] = useState(false);
  const [currentHistoryId, setCurrentHistoryId] = useState<string | null>(null);
  const [selectedCitationId, setSelectedCitationId] = useState<string | null>(null);
  const [documentKinds, setDocumentKinds] = useState<Set<DocumentKind>>(
    () => new Set(Object.keys(DOCUMENT_KIND_LABELS) as DocumentKind[]),
  );
  const askButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const storedUser = getStoredUser();
    void Promise.resolve().then(() => setUser(storedUser));
    getCorpusStatus().then(setCorpus).catch(() => setCorpus(null));
  }, []);

  const refreshHistory = useCallback(async () => {
    setHistoryLoading(true);
    try {
      setHistory(await listQuestionHistory());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "질문 이력을 불러오지 못했습니다.");
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) void Promise.resolve().then(refreshHistory);
  }, [refreshHistory, user]);

  const closeLoginPrompt = useCallback(() => setShowLoginPrompt(false), []);

  async function handleLogin() {
    setError("");
    try {
      setUser(await mockGoogleLogin());
      setShowLoginPrompt(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "목업 로그인에 실패했습니다.");
    }
  }

  async function handleLogout() {
    await logout();
    setUser(null);
    setHistory([]);
    setCurrentHistoryId(null);
  }

  async function handleDeleteAccount() {
    if (!window.confirm("계정을 삭제하면 질문 이력과 관련 데이터가 모두 삭제됩니다. 계속할까요?")) return;
    setError("");
    try {
      await deleteAccount();
      setUser(null);
      setHistory([]);
      setCurrentHistoryId(null);
      setResult(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "계정을 삭제하지 못했습니다.");
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      const answer = await askQuestion({ question, as_of_date: asOf, project_stage: stage });
      setResult(answer);
      setSelectedCitationId(null);
      setCurrentHistoryId(user ? (answer.request_id ?? null) : null);
      if (user) {
        await refreshHistory();
      } else if (claimAnonymousLoginPrompt(sessionStorage)) {
        setShowLoginPrompt(true);
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "연결 오류");
    } finally {
      setLoading(false);
    }
  }

  async function openHistory(item: QuestionHistoryItem) {
    setError("");
    try {
      const detail = item.response ? item : await getQuestionHistory(item.id);
      setQuestion(detail.request.question);
      setAsOf(detail.request.as_of_date);
      setStage(detail.request.project_stage);
      setResult(detail.response);
      setSelectedCitationId(null);
      setCurrentHistoryId(detail.id);
      document.querySelector<HTMLElement>("#answer-panel")?.focus();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "질문 이력을 열지 못했습니다.");
    }
  }

  async function removeHistory(item: QuestionHistoryItem) {
    if (!window.confirm("이 질문 기록을 삭제할까요?")) return;
    try {
      await deleteQuestionHistory(item.id);
      if (currentHistoryId === item.id) {
        setCurrentHistoryId(null);
        setResult(null);
      }
      await refreshHistory();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "질문 기록을 삭제하지 못했습니다.");
    }
  }

  function jumpToCitation(id: string) {
    const citation = result?.citations.find((item) => item.id === id);
    if (citation) {
      const kind = citationDocumentKind(citation);
      setDocumentKinds((current) => new Set([...current, kind]));
    }
    setSelectedCitationId(id);
    requestAnimationFrame(() => {
      const target = document.getElementById(`citation-${id}`);
      target?.focus();
      target?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  }

  function toggleDocumentKind(kind: DocumentKind) {
    setDocumentKinds((current) => {
      const next = new Set(current);
      if (next.has(kind) && next.size > 1) next.delete(kind);
      else next.add(kind);
      return next;
    });
  }

  const visibleCitations = result ? filterCitations(result.citations, documentKinds) : [];
  const corpusProblems = corpus?.items?.filter((item) => item.state !== "ready") ?? [];

  async function exportChecklist() {
    if (!result?.checklist.length) return;
    const input = {
      question,
      asOfDate: asOf,
      projectStage: STAGE_LABELS[stage] ?? stage,
      checklist: result.checklist,
    };
    const filename = `법령-체크리스트-${asOf}`;
    setExporting(true);
    setError("");
    try {
      if (exportFormat === "md") {
        downloadText(`${filename}.md`, renderMarkdown(input), "text/markdown;charset=utf-8");
      } else if (exportFormat === "csv") {
        downloadText(`${filename}.csv`, renderCsv(input), "text/csv;charset=utf-8");
      } else {
        if (!currentHistoryId) throw new Error("PDF 출력본은 로그인 후 저장된 질문에서 만들 수 있습니다.");
        downloadBlob(`${filename}.pdf`, await downloadPdf(currentHistoryId));
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "체크리스트를 내보내지 못했습니다.");
    } finally {
      setExporting(false);
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand">ENERGY / LAW</div>
        <div className="top-actions">
          <div className="status">
            {corpus?.last_successful_sync
              ? `원문 동기화 ${new Date(corpus.last_successful_sync).toLocaleDateString("ko-KR")}`
              : "국가법령정보센터 원문 전용"}
          </div>
          {user ? (
            <div className="user-menu"><span>{user.display_name}</span><button onClick={handleLogout}>로그아웃</button><button className="delete-account" onClick={handleDeleteAccount}>계정 삭제</button></div>
          ) : (
            <button className="header-login" onClick={handleLogin}>Google 목업 로그인</button>
          )}
        </div>
      </header>

      <section className="hero">
        <div className="eyebrow">Distributed energy legal research</div>
        <h1>규제의 경로를<br />근거까지 추적합니다.</h1>
        <p>질문 기준일의 법률·시행령·시행규칙·고시를 연결하고, 모든 핵심 주장 옆에 조문 원문을 붙입니다.</p>
      </section>

      <section className="workspace">
        <div className="left-column">
          <form className="panel" onSubmit={submit}>
            <div className="panel-head"><strong>사업 질문</strong><span className="mode">RAG WORKBENCH</span></div>
            <div className="panel-body">
              <label className="label" htmlFor="question">무엇을 확인할까요?</label>
              <textarea id="question" value={question} onChange={(event) => setQuestion(event.target.value)} maxLength={2000} />
              <div className="filters">
                <div>
                  <label className="label" htmlFor="stage">사업 단계</label>
                  <select id="stage" value={stage} onChange={(event) => setStage(event.target.value)}>
                    {Object.entries(STAGE_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </select>
                </div>
                <div><label className="label" htmlFor="date">법령 기준일</label><input id="date" type="date" value={asOf} onChange={(event) => setAsOf(event.target.value)} /></div>
              </div>
              <fieldset className="document-filters">
                <legend>원문 문서 종류</legend>
                {Object.entries(DOCUMENT_KIND_LABELS).map(([value, label]) => {
                  const kind = value as DocumentKind;
                  return <label key={kind}><input type="checkbox" checked={documentKinds.has(kind)} onChange={() => toggleDocumentKind(kind)} />{label}</label>;
                })}
              </fieldset>
              <button className="ask" disabled={loading} ref={askButton}>{loading ? "근거를 찾는 중…" : "법령 근거 조사"}</button>
              {error && <div className="notice error" role="alert">{error}</div>}
              <div className="notice legal-notice">이 서비스는 법률 자문을 대체하지 않습니다.</div>
              {(corpus?.warnings.length || corpusProblems.length) ? (
                <div className="corpus-warning" role="status">
                  <strong>코퍼스 최신성 확인 필요</strong>
                  {corpus?.warnings.map((warning) => <span key={warning}><SafeText>{warning}</SafeText></span>)}
                  {corpusProblems.map((item) => <span key={item.title}>{item.title}: {item.state === "missing" ? "누락" : "수집 실패"}</span>)}
                </div>
              ) : corpus ? <p className="corpus-ok">허용 목록 코퍼스가 준비되었습니다.</p> : <p className="corpus-warning compact">코퍼스 상태를 확인하지 못했습니다.</p>}
              {!user && <p className="privacy-note">익명 질문은 저장하지 않습니다.</p>}
            </div>
          </form>

          {user && (
            <section className="panel history-panel" aria-labelledby="history-title">
              <div className="panel-head"><strong id="history-title">내 질문 이력</strong><span className="mode">1년 보존</span></div>
              <div className="history-list">
                {historyLoading && <p className="history-empty">불러오는 중…</p>}
                {!historyLoading && history.length === 0 && <p className="history-empty">저장된 질문이 없습니다.</p>}
                {history.map((item) => (
                  <div className="history-item" key={item.id}>
                    <button className="history-open" onClick={() => openHistory(item)}>
                      <strong><SafeText>{item.request.question}</SafeText></strong>
                      <small>{new Date(item.created_at).toLocaleDateString("ko-KR")} · {STAGE_LABELS[item.request.project_stage] ?? item.request.project_stage}</small>
                    </button>
                    <button aria-label={`질문 삭제: ${item.request.question}`} className="history-delete" onClick={() => removeHistory(item)}>삭제</button>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        <div className="research-grid">
          <article className="panel answer-panel" id="answer-panel" tabIndex={-1}>
            <div className="panel-head"><strong>검증된 답변</strong>{result && <span className={`mode ${result.mode === "search_only" ? "search-mode" : ""}`}>{result.mode === "ai" ? "AI + 인용 검증" : "검색 전용"}</span>}</div>
            {!result ? (
              <div className="result-empty">질문을 입력하면 답변과<br />조문 원문을 함께 표시합니다.</div>
            ) : (
              <div className="panel-body">
                <p className="answer-date">법령 기준일 {asOf}</p>
                {result.mode === "search_only" && <div className="search-only" role="status"><strong>검색 전용 결과</strong><span>AI 답변을 생성하지 않고 검색된 원문만 표시합니다.</span></div>}
                <p className="summary"><SafeText>{result.summary}</SafeText></p>
                {result.sections.map((section, index) => (
                  <section className="claim" key={`${section.claim}-${index}`}>
                    <h3><SafeText>{section.claim}</SafeText>{section.citation_ids.map((id) => <button aria-label={`${id} 원문으로 이동`} aria-pressed={selectedCitationId === id} className={`cite ${selectedCitationId === id ? "selected" : ""}`} key={id} onClick={() => jumpToCitation(id)}>{id}</button>)}</h3>
                    <p><SafeText>{section.explanation}</SafeText></p>
                  </section>
                ))}
                {result.checklist.length > 0 && (
                  <section className="claim checklist">
                    <div className="checklist-head"><h3>사업 단계 체크리스트</h3><div className="export-controls"><label className="sr-only" htmlFor="export-format">내보내기 형식</label><select id="export-format" value={exportFormat} onChange={(event) => setExportFormat(event.target.value as ExportFormat)}><option value="md">Markdown</option><option value="csv">CSV</option><option value="pdf">PDF</option></select><button onClick={exportChecklist} disabled={exporting}>{exporting ? "생성 중…" : "내보내기"}</button></div></div>
                    {result.checklist.map((item, index) => <p key={`${item.label}-${index}`}>□ <SafeText>{item.label}</SafeText> {item.citation_ids.map((id) => <button aria-label={`${id} 원문으로 이동`} aria-pressed={selectedCitationId === id} className={`cite ${selectedCitationId === id ? "selected" : ""}`} key={id} onClick={() => jumpToCitation(id)}>{id}</button>)}</p>)}
                  </section>
                )}
                <section className="claim"><h3>범위와 한계</h3>{result.limitations.map((item, index) => <p key={`${item}-${index}`}>· <SafeText>{item}</SafeText></p>)}</section>
              </div>
            )}
          </article>

          <aside className="panel sources-panel">
            <div className="panel-head"><strong>원문 근거</strong><small>{result ? `${visibleCitations.length}/${result.citations.length}건 · ${result.scope}` : `기준일 ${asOf}`}</small></div>
            {!result ? <div className="result-empty">선택한 인용의 조문 원문이<br />이 패널에 표시됩니다.</div> : <div className="panel-body">
              {visibleCitations.length === 0 && <p className="history-empty">선택한 문서 종류에 해당하는 원문이 없습니다.</p>}
              {visibleCitations.map((citation) => (
                <div className={`source ${selectedCitationId === citation.id ? "selected" : ""}`} id={`citation-${citation.id}`} key={citation.id} onClick={() => setSelectedCitationId(citation.id)} onFocus={() => setSelectedCitationId(citation.id)} tabIndex={0}>
                  <strong>{citation.id} · <SafeText>{citation.document_title}</SafeText> <SafeText>{citation.path}</SafeText></strong>
                  <small><SafeText>{citation.version_label}</SafeText></small>
                  <blockquote><SafeText>{citation.quote}</SafeText></blockquote>
                  {citation.source_url && <a href={citation.source_url} rel="noreferrer" target="_blank">국가법령정보센터 원문 열기</a>}
                </div>
              ))}
            </div>}
          </aside>
        </div>
      </section>
      {showLoginPrompt && <LoginPrompt onClose={closeLoginPrompt} onLogin={handleLogin} returnFocus={askButton} />}
    </main>
  );
}
