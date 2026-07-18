"use client";

import type { AuthChangeEvent } from "@supabase/supabase-js";
import { FormEvent, KeyboardEvent, ReactNode, useCallback, useEffect, useRef, useState } from "react";
import {
  askQuestion,
  cancelQuestion,
  deleteAccount,
  deleteConversation,
  downloadPdf,
  getCorpusStatus,
  getStoredUser,
  listConversations,
  listConversationTurns,
  logout,
  startGoogleAuth,
} from "../lib/api-client";
import {
  downloadBlob,
  downloadText,
  type ExportFormat,
  renderCsv,
  renderMarkdown,
} from "../lib/checklist-export";
import { claimAnonymousLoginPrompt } from "../lib/anonymous-prompt";
import { consumeQuestionDraft } from "../lib/composer-state";
import {
  type AnswerPreference,
  isTerraAvailabilityFailure,
  isTerraUnavailable,
  resolveCorpusAnswerMode,
  resolveResponseAnswerMode,
} from "../lib/answer-mode";
import { getEmptyResultMessage } from "../lib/empty-result";
import {
  appendPendingTurn,
  completePendingTurn,
  conversationAnswerText,
  createChatSession,
  failPendingTurn,
  stopPendingTurn,
  selectConversationContext,
  type ChatSession,
} from "../lib/chat-state";
import {
  citationDocumentKind,
  DOCUMENT_KIND_LABELS,
  filterCitations,
  type DocumentKind,
} from "../lib/source-filter";
import type {
  CorpusStatus,
  ConversationSummary,
  MockUser,
  QuestionResponse,
} from "../lib/contracts";
import { SUGGESTED_QUESTIONS } from "../lib/suggested-questions";
import { createClient } from "../lib/supabase/client";
import { SafeText } from "./safe-text";

type AuthDocument = "privacy" | "terms";
type AuthView = "login" | "signup";
type AuthStatus = "checking" | "ready";
type IconName = "account" | "arrow" | "close" | "menu" | "new" | "search" | "trash";

const MODEL_LABELS: Record<AnswerPreference, string> = {
  terra: "NVIDIA Nemotron · 근거 답변",
  search_only: "검색 전용 · 원문만",
};

export function oauthRedirectMessage(search: string): string | null {
  const status = new URLSearchParams(search).get("auth");
  if (status !== "error") return null;
  return "Google 로그인을 완료하지 못했습니다. 인증을 취소했거나 요청이 만료되었을 수 있습니다. 다시 시도해 주세요.";
}

export function authEventAction(event: string): "clear" | "hydrate" | "ignore" {
  if (event === "SIGNED_OUT") return "clear";
  if (event === "SIGNED_IN" || event === "USER_UPDATED") return "hydrate";
  return "ignore";
}

function Icon({ name }: { name: IconName }) {
  const paths: Record<IconName, ReactNode> = {
    account: <><circle cx="12" cy="8" r="3.5" /><path d="M5 20c.7-4 3-6 7-6s6.3 2 7 6" /></>,
    arrow: <><path d="M12 19V5" /><path d="m6 11 6-6 6 6" /></>,
    close: <><path d="m6 6 12 12" /><path d="M18 6 6 18" /></>,
    menu: <><path d="M4 7h16" /><path d="M4 12h16" /><path d="M4 17h16" /></>,
    new: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
    search: <><circle cx="11" cy="11" r="6" /><path d="m16 16 4 4" /></>,
    trash: <><path d="M5 7h14" /><path d="m9 7 1-2h4l1 2" /><path d="m8 10 1 9h6l1-9" /></>,
  };
  return <svg aria-hidden="true" className="icon" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.8">{paths[name]}</svg>;
}

function Dialog({ children, onClose, titleId }: { children: ReactNode; onClose: () => void; titleId: string }) {
  const dialog = useRef<HTMLElement>(null);
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    dialog.current?.focus();
    const closeOnEscape = (event: globalThis.KeyboardEvent) => event.key === "Escape" && onClose();
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("keydown", closeOnEscape);
      previous?.focus();
    };
  }, [onClose]);

  return (
    <div className="modal-backdrop" onMouseDown={onClose} role="presentation">
      <section aria-labelledby={titleId} aria-modal="true" className="modal" onMouseDown={(event) => event.stopPropagation()} ref={dialog} role="dialog" tabIndex={-1}>
        <button aria-label="닫기" className="icon-button modal-close" onClick={onClose}><Icon name="close" /></button>
        {children}
      </section>
    </div>
  );
}

function AuthDialog({ notice, onClose, onGoogleContinue, onSwitch, view }: {
  notice: string;
  onClose: () => void;
  onGoogleContinue: (view: AuthView) => void;
  onSwitch: (view: AuthView) => void;
  view: AuthView;
}) {
  const [acceptTerms, setAcceptTerms] = useState(false);
  const [acceptPrivacy, setAcceptPrivacy] = useState(false);
  const [documentView, setDocumentView] = useState<AuthDocument | null>(null);
  const signupReady = acceptTerms && acceptPrivacy;
  const documentTitle = documentView === "terms" ? "서비스 이용약관" : "개인정보 처리방침";

  return (
    <Dialog onClose={onClose} titleId="auth-title">
      <div className="auth-brand"><div className="modal-mark">EL</div><span>Energy Law</span></div>
      {documentView ? <>
        <p className="eyebrow">Policy preview</p>
        <h2 id="auth-title">{documentTitle}</h2>
        <div className="policy-preview">
          <span>UI 초안 · 본문 미확정</span>
          <p>최종 법률 검토를 거친 문서와 버전이 인증 구현 단계에서 연결됩니다.</p>
          <h3>이 화면에서 안내할 내용</h3>
          <ul>{documentView === "terms" ? <>
            <li>서비스의 법률 조사 범위와 법률 자문 대체 불가</li>
            <li>사용자 입력 책임과 허용되지 않는 사용</li>
            <li>서비스 변경·중단·계정 종료 조건</li>
          </> : <>
            <li>Google 계정 식별정보와 질문 이력의 처리 목적</li>
            <li>질문 기록 1년 보관 및 계정 삭제 전파</li>
            <li>사용자 권리, 국외 이전, 문의 경로</li>
          </>}</ul>
        </div>
        <button className="auth-back" onClick={() => setDocumentView(null)}>회원가입으로 돌아가기</button>
      </> : view === "login" ? <>
        <p className="eyebrow">Welcome back</p>
        <h2 id="auth-title">다시 만나 반갑습니다</h2>
        <p className="modal-copy">Google 계정으로 로그인하고 저장한 질문, 인용 원문, 체크리스트를 이어서 확인하세요.</p>
        <button className="google-login" onClick={() => onGoogleContinue("login")}><span aria-hidden="true">G</span> Google로 로그인</button>
        <div className="auth-assurances" aria-label="로그인 데이터 정책">
          <span>질문 기록 1년 보관</span><span>익명 질문 소급 저장 안 함</span>
        </div>
        <p className="auth-switch">처음 방문하셨나요? <button onClick={() => onSwitch("signup")}>계정 만들기</button></p>
      </> : <>
        <p className="eyebrow">Create account</p>
        <h2 id="auth-title">연구 기록을 이어갈 계정을 만드세요</h2>
        <p className="modal-copy">별도의 비밀번호 없이 Google 계정으로 가입합니다. 로그인 후 질문부터 계정에 저장됩니다.</p>
        <div className="signup-benefits">
          <div><strong>질문 이력</strong><span>왼쪽 목록에서 이전 조사를 다시 엽니다.</span></div>
          <div><strong>내 데이터 통제</strong><span>계정 삭제 시 연결된 질문과 내보내기를 함께 삭제합니다.</span></div>
        </div>
        <fieldset className="consent-list">
          <legend>필수 동의</legend>
          <label><input checked={acceptTerms} onChange={(event) => setAcceptTerms(event.target.checked)} type="checkbox" /><span><strong>서비스 이용약관 동의</strong><small>서비스 범위와 사용자 책임을 확인했습니다.</small></span><button aria-label="서비스 이용약관 보기" onClick={() => setDocumentView("terms")} type="button">보기</button></label>
          <label><input checked={acceptPrivacy} onChange={(event) => setAcceptPrivacy(event.target.checked)} type="checkbox" /><span><strong>개인정보 처리방침 동의</strong><small>질문 이력의 1년 보관 및 삭제 정책을 확인했습니다.</small></span><button aria-label="개인정보 처리방침 보기" onClick={() => setDocumentView("privacy")} type="button">보기</button></label>
        </fieldset>
        <button className="google-login" disabled={!signupReady} onClick={() => onGoogleContinue("signup")}><span aria-hidden="true">G</span> Google로 계정 만들기</button>
        <p className="auth-switch">이미 계정이 있나요? <button onClick={() => onSwitch("login")}>로그인</button></p>
      </>}
      {!documentView && notice && <div className="auth-notice" role="status"><strong>연결 준비 중</strong><span>{notice}</span></div>}
      {!documentView && <p className="fine-print">이 서비스는 법률 자문을 대체하지 않습니다.</p>}
    </Dialog>
  );
}

function AccountDialog({ corpus, onClose, onDelete, onLogout, user }: {
  corpus: CorpusStatus | null;
  onClose: () => void;
  onDelete: () => Promise<void>;
  onLogout: () => Promise<void>;
  user: MockUser;
}) {
  return (
    <Dialog onClose={onClose} titleId="account-title">
      <p className="eyebrow">Account dashboard</p>
      <h2 id="account-title">계정 및 모델 정책</h2>
      <div className="account-profile">
        <div className="avatar">{user.display_name.slice(0, 1)}</div>
        <div><strong>{user.display_name}</strong><span>{user.email}</span></div>
      </div>
      <dl className="policy-grid">
        <div><dt>로그인</dt><dd>Google</dd></div>
        <div><dt>질문 보존</dt><dd>생성일로부터 1년</dd></div>
        <div><dt>생성 모델</dt><dd>gpt-5.6-terra 전용</dd></div>
        <div><dt>현재 상태</dt><dd className={corpus?.ai_available ? "available" : "limited"}>{corpus?.ai_available ? "NVIDIA AI 사용 가능" : "검색 전용"}</dd></div>
        <div><dt>장애 시 동작</dt><dd>다른 모델 없이 검색 전용</dd></div>
        <div><dt>계정 사용 한도</dt><dd>AI 10회/일 · 검색 100회/일 (베타)</dd></div>
      </dl>
      <div className="account-actions"><button onClick={onLogout}>로그아웃</button><button className="danger" onClick={onDelete}>계정 삭제</button></div>
    </Dialog>
  );
}

function AnswerView({
  asOf,
  documentKinds,
  exportFormat,
  exporting,
  messageId,
  onCitation,
  onExport,
  onExportFormat,
  onRefine,
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
  onRefine: () => void;
  question: string;
  response: QuestionResponse;
  selectedCitationId: string | null;
}) {
  const emptyResult = getEmptyResultMessage(response, question);
  const citations = filterCitations(response.citations, documentKinds);
  return <>
    <div className="answer-meta"><span className={response.mode === "ai" ? "mode-badge" : "mode-badge search"}>{response.mode === "ai" ? "NVIDIA Nemotron · 인용 검증" : "검색 전용"}</span><span>기준일 {asOf}</span></div>
    {emptyResult && <section aria-live="polite" className="empty-result" role="status"><h2>{emptyResult.title}</h2><p><strong>원인</strong> <SafeText>{emptyResult.reason}</SafeText></p><p><strong>다시 검색하려면</strong> <SafeText>{emptyResult.guidance}</SafeText></p><button onClick={onRefine}>질문 구체화하기</button></section>}
    {!emptyResult && <p className="summary"><SafeText>{response.summary}</SafeText></p>}
    {response.sections.map((section, index) => <section className="claim" key={`${section.claim}-${index}`}><h2><SafeText>{section.claim}</SafeText></h2><p><SafeText>{section.explanation}</SafeText></p><div className="citation-links">{section.citation_ids.map((id) => <button className={selectedCitationId === `${messageId}:${id}` ? "selected" : ""} key={id} onClick={() => onCitation(messageId, response, id)}>{id} 원문</button>)}</div></section>)}
    {response.checklist.length > 0 && <section className="checklist"><div className="section-title-row"><h2>확인 체크리스트</h2><div className="export-controls"><select aria-label="내보내기 형식" value={exportFormat} onChange={(event) => onExportFormat(event.target.value as ExportFormat)}><option value="md">Markdown</option><option value="csv">CSV</option><option value="pdf">PDF</option></select><button disabled={exporting} onClick={() => onExport(response, question, asOf)}>{exporting ? "생성 중" : "내보내기"}</button></div></div>{response.checklist.map((item, index) => <div className="check-item" key={`${item.label}-${index}`}><span aria-hidden="true">□</span><p><SafeText>{item.label}</SafeText>{item.citation_ids.map((id) => <button className="inline-cite" key={id} onClick={() => onCitation(messageId, response, id)}>{id}</button>)}</p></div>)}</section>}
    {citations.length > 0 && <section className="sources"><h2>원문 근거 <span>{citations.length}건</span></h2>{citations.map((citation) => <details className={selectedCitationId === `${messageId}:${citation.id}` ? "source selected" : "source"} id={`citation-${messageId}-${citation.id}`} key={citation.id} open={selectedCitationId === `${messageId}:${citation.id}`}><summary><span><strong>{citation.id} · <SafeText>{citation.document_title}</SafeText> <SafeText>{citation.path}</SafeText></strong><small><SafeText>{citation.version_label}</SafeText></small></span></summary><blockquote><SafeText>{citation.quote}</SafeText></blockquote></details>)}</section>}
    <section className="limitations"><h2>범위와 한계</h2>{response.limitations.map((item, index) => <p key={`${item}-${index}`}>· <SafeText>{item}</SafeText></p>)}</section>
  </>;
}

export default function Home() {
  const [question, setQuestion] = useState("");
  const [asOf, setAsOf] = useState(new Date().toISOString().slice(0, 10));
  const [answerPreference, setAnswerPreference] = useState<AnswerPreference>("terra");
  const [result, setResult] = useState<QuestionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [modeNotice, setModeNotice] = useState("");
  const [corpus, setCorpus] = useState<CorpusStatus | null>(null);
  const [terraUnavailableFromResponse, setTerraUnavailableFromResponse] = useState(false);
  const [user, setUser] = useState<MockUser | null>(null);
  const [authStatus, setAuthStatus] = useState<AuthStatus>("checking");
  const [history, setHistory] = useState<ConversationSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyLoadingMore, setHistoryLoadingMore] = useState(false);
  const [historyHasMore, setHistoryHasMore] = useState(false);
  const [showAuth, setShowAuth] = useState(false);
  const [authView, setAuthView] = useState<AuthView>("login");
  const [authNotice, setAuthNotice] = useState("");
  const [showAccount, setShowAccount] = useState(false);
  const [showAnonymousNudge, setShowAnonymousNudge] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [exportFormat, setExportFormat] = useState<ExportFormat>("md");
  const [exporting, setExporting] = useState(false);
  const [currentHistoryId, setCurrentHistoryId] = useState<string | null>(null);
  const [selectedCitationId, setSelectedCitationId] = useState<string | null>(null);
  const [submittedQuestion, setSubmittedQuestion] = useState("");
  const [activeChat, setActiveChat] = useState<ChatSession>(() => createChatSession(crypto.randomUUID()));
  const [turnCursor, setTurnCursor] = useState<string | null>(null);
  const [turnHasMore, setTurnHasMore] = useState(false);
  const [turnLoadingMore, setTurnLoadingMore] = useState(false);
  const [documentKinds, setDocumentKinds] = useState<Set<DocumentKind>>(() => new Set(Object.keys(DOCUMENT_KIND_LABELS) as DocumentKind[]));
  const composer = useRef<HTMLTextAreaElement>(null);
  const authEpoch = useRef(0);
  const activeRequest = useRef<{ id: string; controller: AbortController } | null>(null);
  const historySentinel = useRef<HTMLDivElement>(null);
  const historyCursorRef = useRef<string | null>(null);

  const clearAuthenticatedWorkspace = useCallback(() => {
    authEpoch.current += 1;
    setUser(null);
    setHistory([]);
    historyCursorRef.current = null;
    setHistoryHasMore(false);
    setHistoryLoading(false);
    setQuestion("");
    setSubmittedQuestion("");
    setResult(null);
    activeRequest.current?.controller.abort();
    activeRequest.current = null;
    setActiveChat(createChatSession(crypto.randomUUID()));
    setCurrentHistoryId(null);
    setSelectedCitationId(null);
    setShowAccount(false);
    setShowAnonymousNudge(false);
    setAuthStatus("ready");
  }, []);

  useEffect(() => {
    let active = true;
    let hydrationInFlight = false;
    const hydrateUser = async () => {
      if (hydrationInFlight) return;
      hydrationInFlight = true;
      const epoch = ++authEpoch.current;
      setAuthStatus("checking");
      try {
        const storedUser = await getStoredUser();
        if (active && authEpoch.current === epoch) setUser(storedUser);
      } catch (cause) {
        if (active && authEpoch.current === epoch) {
          setUser(null);
          setError(cause instanceof Error ? cause.message : "로그인 정보를 확인하지 못했습니다.");
        }
      } finally {
        if (active && authEpoch.current === epoch) setAuthStatus("ready");
        hydrationInFlight = false;
      }
    };

    const oauthMessage = oauthRedirectMessage(window.location.search);
    if (oauthMessage) {
      void Promise.resolve().then(() => {
        if (!active) return;
        setError(oauthMessage);
        setAuthNotice(oauthMessage);
        setAuthView("login");
        setShowAuth(true);
      });
    }
    if (new URLSearchParams(window.location.search).has("auth")) {
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.hash}`);
    }

    void hydrateUser();
    const { data: { subscription } } = createClient().auth.onAuthStateChange((event: AuthChangeEvent) => {
      const action = authEventAction(event);
      if (action === "clear") {
        clearAuthenticatedWorkspace();
      } else if (action === "hydrate") {
        void Promise.resolve().then(hydrateUser);
      }
    });
    getCorpusStatus().then((status) => {
      setCorpus(status);
      const resolution = resolveCorpusAnswerMode(status);
      if (!status.ai_available) {
        setModeNotice(resolution.notice ?? "");
        setAnswerPreference(resolution.preference);
      }
    }).catch(() => setCorpus(null));
    return () => {
      active = false;
      subscription.unsubscribe();
    };
  }, [clearAuthenticatedWorkspace]);

  const refreshHistory = useCallback(async (append = false) => {
    const epoch = authEpoch.current;
    if (append) setHistoryLoadingMore(true);
    else setHistoryLoading(true);
    try {
      const page = await listConversations(append ? historyCursorRef.current : null);
      if (authEpoch.current === epoch) {
        setHistory((current) => {
          const values = append ? [...current, ...page.items] : page.items;
          return [...new Map(values.map((item) => [item.id, item])).values()];
        });
        historyCursorRef.current = page.next_cursor ?? null;
        setHistoryHasMore(page.has_more);
      }
    } catch (cause) {
      if (authEpoch.current === epoch) setError(cause instanceof Error ? cause.message : "질문 이력을 불러오지 못했습니다.");
    } finally {
      if (authEpoch.current === epoch) {
        setHistoryLoading(false);
        setHistoryLoadingMore(false);
      }
    }
  }, []);

  useEffect(() => {
    if (user) void Promise.resolve().then(() => refreshHistory());
  }, [refreshHistory, user]);

  useEffect(() => {
    const node = historySentinel.current;
    if (!node || !user || !historyHasMore || historyLoadingMore) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) void refreshHistory(true);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, [historyHasMore, historyLoadingMore, refreshHistory, user]);

  const closeAuth = useCallback(() => {
    setShowAuth(false);
    setAuthNotice("");
  }, []);
  const closeAccount = useCallback(() => setShowAccount(false), []);

  function openAuth(view: AuthView = "login") {
    setAuthView(view);
    setAuthNotice("");
    setShowAuth(true);
  }

  function switchAuthView(view: AuthView) {
    setAuthView(view);
    setAuthNotice("");
  }

  async function handleGoogleAuth(view: AuthView) {
    setAuthNotice("Google 인증 화면으로 이동합니다.");
    try {
      await startGoogleAuth(view);
    } catch (cause) {
      setAuthNotice(cause instanceof Error ? cause.message : "Google 로그인을 시작하지 못했습니다.");
    }
  }

  async function handleLogout() {
    try {
      await logout();
      clearAuthenticatedWorkspace();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "로그아웃하지 못했습니다.");
    }
  }

  async function handleDeleteAccount() {
    if (!window.confirm("계정을 삭제하면 질문 이력과 관련 데이터가 모두 삭제됩니다. 계속할까요?")) return;
    try {
      await deleteAccount();
      setUser(null);
      setHistory([]);
      startNewChat();
      setShowAccount(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "계정을 삭제하지 못했습니다.");
    }
  }

  function startNewChat(seed = "") {
    activeRequest.current?.controller.abort();
    activeRequest.current = null;
    setQuestion(seed);
    setSubmittedQuestion("");
    setResult(null);
    setError("");
    setCurrentHistoryId(null);
    setSelectedCitationId(null);
    setActiveChat(createChatSession(crypto.randomUUID()));
    setTurnCursor(null);
    setTurnHasMore(false);
    setSidebarOpen(false);
    requestAnimationFrame(() => composer.current?.focus());
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (loading) return;
    const submission = consumeQuestionDraft(question);
    if (!submission) return;
    const { submittedQuestion: trimmed, nextDraft } = submission;
    const requestId = crypto.randomUUID();
    const controller = new AbortController();
    const contextSelection = selectConversationContext(activeChat, trimmed);
    const pending = appendPendingTurn(activeChat, {
      requestId,
      userMessageId: crypto.randomUUID(),
      assistantMessageId: crypto.randomUUID(),
      question: trimmed,
      asOf,
      rolloverSessionId: crypto.randomUUID(),
    });
    activeRequest.current = { id: requestId, controller };
    setActiveChat(pending.session);
    setLoading(true);
    setError("");
    setSubmittedQuestion(trimmed);
    setQuestion(nextDraft);
    requestAnimationFrame(() => composer.current?.focus());
    const requestedAnswerMode = terraUnavailable ? "search_only" : answerPreference;
    try {
      const answer = await askQuestion({
        client_request_id: requestId,
        question: trimmed,
        as_of_date: asOf,
        project_stage: "planning",
        answer_mode: requestedAnswerMode,
        ...(!contextSelection.rolledOver && contextSelection.turns.length > 0
          ? { conversation_context: contextSelection.turns.map((turn) => ({
              question: turn.question,
              answer: conversationAnswerText(turn.response),
            })) }
          : {}),
        ...(pending.rolledOver || activeChat.messages.length === 0
          ? {}
          : { conversation_id: activeChat.id }),
      }, controller.signal);
      if (activeRequest.current?.id !== requestId) return;
      const resolution = resolveResponseAnswerMode(requestedAnswerMode, answer);
      setModeNotice(resolution.notice ?? "");
      setAnswerPreference(resolution.preference);
      if (isTerraAvailabilityFailure(answer.fallback_reason)) {
        setTerraUnavailableFromResponse(true);
        setCorpus((current) => current ? {
          ...current,
          ai_available: false,
          ai_unavailable_reason: answer.fallback_reason === "ai_disabled" ? "ai_disabled" : "quota_exhausted",
        } : current);
      }
      setResult(answer);
      setActiveChat((current) => ({
        ...completePendingTurn(current, requestId, answer),
        id: answer.conversation_id ?? current.id,
      }));
      setSelectedCitationId(null);
      setCurrentHistoryId(user ? (answer.request_id ?? null) : null);
      if (user) {
        historyCursorRef.current = null;
        await refreshHistory();
      }
      else if (claimAnonymousLoginPrompt(sessionStorage)) setShowAnonymousNudge(true);
    } catch (cause) {
      if (activeRequest.current?.id !== requestId) return;
      if (cause instanceof DOMException && cause.name === "AbortError") {
        setActiveChat((current) => stopPendingTurn(current, requestId));
      } else {
        const message = cause instanceof Error ? cause.message : "연결 오류";
        setActiveChat((current) => failPendingTurn(current, requestId, message));
        setError(message);
      }
    } finally {
      if (activeRequest.current?.id === requestId) {
        activeRequest.current = null;
        setLoading(false);
      }
    }
  }

  function stopGeneration() {
    const request = activeRequest.current;
    if (!request) return;
    void cancelQuestion(request.id).catch(() => undefined);
    request.controller.abort();
    setActiveChat((current) => stopPendingTurn(current, request.id));
    activeRequest.current = null;
    setLoading(false);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  async function openHistory(item: ConversationSummary) {
    setError("");
    try {
      activeRequest.current?.controller.abort();
      const page = await listConversationTurns(item.id);
      const ordered = [...page.items].reverse();
      const messages = ordered.flatMap((detail) => [
        { id: `user-${detail.id}`, role: "user" as const, text: detail.request.question, asOf: detail.request.as_of_date, status: "sent" as const },
        { id: `assistant-${detail.id}`, role: "assistant" as const, requestId: detail.id, status: "complete" as const, response: detail.response },
      ]);
      const latest = ordered.at(-1);
      if (!latest) throw new Error("대화에 표시할 질문이 없습니다.");
      setActiveChat({ id: item.id, title: item.title, messages, contextMessageCount: item.turn_count * 2 });
      setTurnCursor(page.next_cursor ?? null);
      setTurnHasMore(page.has_more);
      setQuestion("");
      setSubmittedQuestion(latest.request.question);
      setAsOf(latest.request.as_of_date);
      const requestedAnswerMode = latest.request.answer_mode ?? (latest.response.mode === "ai" ? "terra" : "search_only");
      const resolution = resolveResponseAnswerMode(requestedAnswerMode, latest.response);
      setModeNotice(resolution.notice ?? "");
      setAnswerPreference(resolution.preference);
      setResult(latest.response);
      setSelectedCitationId(null);
      setCurrentHistoryId(latest.id);
      setSidebarOpen(false);
      document.querySelector<HTMLElement>("#conversation")?.focus();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "질문 이력을 열지 못했습니다.");
    }
  }

  async function removeHistory(item: ConversationSummary) {
    if (!window.confirm("이 대화 기록 전체를 삭제할까요?")) return;
    try {
      await deleteConversation(item.id);
      if (activeChat.id === item.id) startNewChat();
      setHistory((current) => current.filter((entry) => entry.id !== item.id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "질문 기록을 삭제하지 못했습니다.");
    }
  }

  async function loadOlderTurns() {
    if (!turnHasMore || !turnCursor || turnLoadingMore) return;
    setTurnLoadingMore(true);
    try {
      const page = await listConversationTurns(activeChat.id, turnCursor);
      const olderMessages = [...page.items].reverse().flatMap((detail) => [
        { id: `user-${detail.id}`, role: "user" as const, text: detail.request.question, asOf: detail.request.as_of_date, status: "sent" as const },
        { id: `assistant-${detail.id}`, role: "assistant" as const, requestId: detail.id, status: "complete" as const, response: detail.response },
      ]);
      setActiveChat((current) => ({ ...current, messages: [...olderMessages, ...current.messages] }));
      setTurnCursor(page.next_cursor ?? null);
      setTurnHasMore(page.has_more);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "이전 대화를 불러오지 못했습니다.");
    } finally {
      setTurnLoadingMore(false);
    }
  }

  function jumpToCitation(messageId: string, response: QuestionResponse, id: string) {
    const citation = response.citations.find((item) => item.id === id);
    if (citation) setDocumentKinds((current) => new Set([...current, citationDocumentKind(citation)]));
    setSelectedCitationId(`${messageId}:${id}`);
    requestAnimationFrame(() => document.getElementById(`citation-${messageId}-${id}`)?.scrollIntoView({ behavior: "smooth", block: "center" }));
  }

  function toggleDocumentKind(kind: DocumentKind) {
    setDocumentKinds((current) => {
      const next = new Set(current);
      if (next.has(kind) && next.size > 1) next.delete(kind);
      else next.add(kind);
      return next;
    });
  }

  async function exportChecklist(exportResult = result, exportQuestion = submittedQuestion, exportAsOf = asOf) {
    if (!exportResult?.checklist.length) return;
    const input = { question: exportQuestion, asOfDate: exportAsOf, projectStage: "일반 조사", checklist: exportResult.checklist };
    const filename = `법령-체크리스트-${exportAsOf}`;
    setExporting(true);
    setError("");
    try {
      if (exportFormat === "md") downloadText(`${filename}.md`, renderMarkdown(input), "text/markdown;charset=utf-8");
      else if (exportFormat === "csv") downloadText(`${filename}.csv`, renderCsv(input), "text/csv;charset=utf-8");
      else {
        const historyId = exportResult.request_id ?? currentHistoryId;
        if (!historyId) throw new Error("PDF 출력본은 로그인 후 저장된 질문에서 만들 수 있습니다.");
        downloadBlob(`${filename}.pdf`, await downloadPdf(historyId));
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "체크리스트를 내보내지 못했습니다.");
    } finally {
      setExporting(false);
    }
  }

  const terraUnavailable = terraUnavailableFromResponse || isTerraUnavailable(corpus);

  function refineQuestion() {
    setShowAnonymousNudge(false);
    requestAnimationFrame(() => {
      composer.current?.focus();
      composer.current?.setSelectionRange(0, composer.current.value.length);
    });
  }

  return (
    <main className="app-shell">
      {sidebarOpen && <button aria-label="사이드바 닫기" className="sidebar-scrim" onClick={() => setSidebarOpen(false)} />}
      <aside className={`sidebar ${sidebarOpen ? "open" : ""}`}>
        <div className="sidebar-brand"><div className="brand-mark">EL</div><span>Energy Law</span><button aria-label="사이드바 닫기" className="icon-button sidebar-close" onClick={() => setSidebarOpen(false)}><Icon name="close" /></button></div>
        <button className="new-chat" onClick={() => startNewChat()}><Icon name="new" />새 질문</button>
        <div className="history-heading"><span>질문 기록</span>{user && <small>1년 보존</small>}</div>
        <nav aria-label="저장된 질문" className="history-list">
          {authStatus === "checking" && <p aria-live="polite" className="history-empty">로그인 상태 확인 중…</p>}
          {authStatus === "ready" && !user && <div className="sidebar-empty"><p>로그인하면 이전 질문을 다시 열 수 있습니다.</p><button onClick={() => openAuth("login")}>로그인</button></div>}
          {user && historyLoading && <p className="history-empty">불러오는 중…</p>}
          {user && !historyLoading && history.length === 0 && <p className="history-empty">저장된 질문이 없습니다.</p>}
          {user && history.map((item) => (
            <div className={`history-item ${activeChat.id === item.id ? "active" : ""}`} key={item.id}>
              <button className="history-open" onClick={() => openHistory(item)} title={item.title}><span className="history-title"><SafeText>{item.title}</SafeText></span><small>{new Date(item.updated_at).toLocaleDateString("ko-KR")}</small></button>
              <button aria-label={`대화 삭제: ${item.title}`} className="history-delete" onClick={() => removeHistory(item)}><Icon name="trash" /></button>
            </div>
          ))}
          {user && historyHasMore && <div className="history-sentinel" ref={historySentinel}>{historyLoadingMore ? "불러오는 중…" : <button className="history-more" onClick={() => refreshHistory(true)}>더 보기</button>}</div>}
        </nav>
        <div className="sidebar-footer">
          {user ? <button className="account-button" onClick={() => setShowAccount(true)}><div className="avatar small">{user.display_name.slice(0, 1)}</div><span><strong>{user.display_name}</strong><small>계정 및 모델 정책</small></span></button>
            : authStatus === "checking"
              ? <button aria-label="로그인 상태 확인 중" className="account-button" disabled><Icon name="account" /><span><strong>확인 중…</strong><small>로그인 상태 복원</small></span></button>
              : <button className="account-button" onClick={() => openAuth("login")}><Icon name="account" /><span><strong>로그인</strong><small>질문 기록 저장</small></span></button>}
        </div>
      </aside>

      <section className="main-column">
        <header className="chat-header">
          <button aria-label="메뉴 열기" className="icon-button mobile-menu" onClick={() => setSidebarOpen(true)}><Icon name="menu" /></button>
          <label className="model-picker"><span className="sr-only">응답 모델</span><select aria-label="응답 모델" value={answerPreference} onChange={(event) => { setAnswerPreference(event.target.value as AnswerPreference); setModeNotice(""); }}>
            <option disabled={terraUnavailable} value="terra">{MODEL_LABELS.terra}{terraUnavailable ? " · 현재 사용 불가" : ""}</option>
            <option value="search_only">{MODEL_LABELS.search_only}</option>
            <option disabled>다른 생성 모델 · 미지원</option>
          </select></label>
          <div className="header-actions">{user ? <button className="avatar-button" aria-label="계정 대시보드" onClick={() => setShowAccount(true)}>{user.display_name.slice(0, 1)}</button> : authStatus === "checking" ? <button aria-label="로그인 상태 확인 중" className="login-button" disabled>확인 중…</button> : <button className="login-button" onClick={() => openAuth("login")}>로그인</button>}</div>
        </header>

        {modeNotice && <div aria-live="polite" className="mode-notice" role="status"><span>{modeNotice}</span><button aria-label="모델 전환 알림 닫기" onClick={() => setModeNotice("")}><Icon name="close" /></button></div>}

        <div className={`chat-scroll ${result || loading ? "has-conversation" : ""}`} onScroll={(event) => { if (event.currentTarget.scrollTop < 80) void loadOlderTurns(); }}>
          <section className="conversation" id="conversation" tabIndex={-1}>
            {activeChat.messages.length === 0 ? (
              <div className="welcome">
                <div className="welcome-mark"><Icon name="search" /></div>
                <p className="eyebrow">Energy Law Research System</p>
                <h1>질문에서 근거 원문까지,<br />한 흐름으로 확인하세요.</h1>
                <p className="welcome-copy">국가법령정보 공동활용 Open API의 법령·시행령·시행규칙·행정규칙만 검색합니다. 핵심 주장마다 확인 가능한 조문을 연결합니다.</p>
                <div className="suggestions">{SUGGESTED_QUESTIONS.map((suggestion) => <button key={suggestion} onClick={() => startNewChat(suggestion)}>{suggestion}<Icon name="arrow" /></button>)}</div>
                <div className="capabilities"><span>근거 인용</span><span>기준일 검색</span><span>체크리스트</span></div>
              </div>
            ) : (
              <>
                {activeChat.rolloverNotice && <div aria-live="polite" className="context-rollover" role="status">{activeChat.rolloverNotice} 컨텍스트는 새로 시작됩니다.</div>}
                {turnHasMore && <button className="history-more" disabled={turnLoadingMore} onClick={loadOlderTurns}>{turnLoadingMore ? "불러오는 중…" : "이전 대화 불러오기"}</button>}
                {activeChat.messages.map((message, index) => {
                  const previous = activeChat.messages[index - 1];
                  return message.role === "user"
                  ? <article className="message user-message chat-turn" key={message.id}><div className="message-body"><SafeText>{message.text}</SafeText></div></article>
                  : <article className="message assistant-message" key={message.id}><div className="assistant-avatar">EL</div><div className="message-content">
                    {message.status === "pending" && <div className="thinking"><span /><span /><span />근거를 확인하고 있습니다</div>}
                    {message.status === "stopped" && <p className="stopped-response">응답 대기를 중지했습니다.</p>}
                    {message.status === "error" && <p className="stopped-response">{message.error}</p>}
                    {message.status === "complete" && message.response && previous?.role === "user" && <AnswerView asOf={previous.asOf} documentKinds={documentKinds} exportFormat={exportFormat} exporting={exporting} messageId={message.id} onCitation={jumpToCitation} onExport={(value, prompt, date) => void exportChecklist(value, prompt, date)} onExportFormat={setExportFormat} onRefine={refineQuestion} question={previous.text} response={message.response} selectedCitationId={selectedCitationId} />}
                  </div></article>;
                })}
                {showAnonymousNudge && !user && <aside className="login-nudge"><div><strong>이 질문을 다시 열어보고 싶나요?</strong><p>지금 로그인해도 현재 익명 질문은 저장되지 않습니다. 다음 질문부터 기록됩니다.</p></div><button onClick={() => openAuth("login")}>로그인</button><button aria-label="안내 닫기" className="icon-button" onClick={() => setShowAnonymousNudge(false)}><Icon name="close" /></button></aside>}
              </>
            )}
          </section>
        </div>

        <div className="composer-wrap">
          {error && <div className="error-banner" role="alert">{error}<button aria-label="오류 닫기" onClick={() => setError("")}><Icon name="close" /></button></div>}
          <form className="composer" onSubmit={submit}>
            <textarea aria-label="법령 질문" maxLength={2000} onChange={(event) => setQuestion(event.target.value)} onKeyDown={handleComposerKeyDown} placeholder="에너지 법령을 질문하세요" ref={composer} rows={1} value={question} />
            <div className="composer-footer">
              <fieldset className="document-filters"><legend className="sr-only">원문 문서 종류</legend>{Object.entries(DOCUMENT_KIND_LABELS).map(([value, label]) => { const kind = value as DocumentKind; return <label key={kind}><input checked={documentKinds.has(kind)} onChange={() => toggleDocumentKind(kind)} type="checkbox" />{label}</label>; })}</fieldset>
              <div className="composer-actions"><label className="date-control"><span>기준일</span><input aria-label="법령 기준일" onChange={(event) => setAsOf(event.target.value)} type="date" value={asOf} /></label>{loading ? <button aria-label="응답 생성 중지" className="send-button stop-button" onClick={stopGeneration} type="button" /> : <button aria-label="법령 근거 조사" className="send-button" disabled={question.trim().length < 2}><Icon name="arrow" /></button>}</div>
            </div>
          </form>
          <p className="composer-disclaimer">법률 자문을 대체하지 않습니다. 중요한 결정은 원문과 전문가 검토를 함께 확인하세요.</p>
        </div>
      </section>

      {showAuth && <AuthDialog notice={authNotice} onClose={closeAuth} onGoogleContinue={handleGoogleAuth} onSwitch={switchAuthView} view={authView} />}
      {showAccount && user && <AccountDialog corpus={corpus} onClose={closeAccount} onDelete={handleDeleteAccount} onLogout={handleLogout} user={user} />}
    </main>
  );
}
