import { describe, expect, it } from "vitest";
import type { QuestionResponse } from "./contracts";
import {
  CONTEXT_ROLLOVER_NOTICE,
  DEFAULT_INPUT_CONTEXT_TOKENS,
  MESSAGE_TOKEN_OVERHEAD,
  appendPendingTurn,
  completePendingTurn,
  createChatSession,
  ellipsizeChatTitle,
  estimateTextTokens,
  failPendingTurn,
  firstQuestionTitle,
  selectConversationContext,
  stopPendingTurn,
  type ChatMessage,
  type ChatSession,
} from "./chat-state";

const response: QuestionResponse = {
  request_id: "response-1",
  mode: "search_only",
  summary: "검색 결과",
  scope: "현행 법령",
  sections: [],
  checklist: [],
  citations: [],
  limitations: [],
};

function pendingInput(index: number) {
  return {
    requestId: `request-${index}`,
    userMessageId: `user-${index}`,
    assistantMessageId: `assistant-${index}`,
    question: `  첫 질문 ${index}\n입니다  `,
    asOf: "2026-07-18",
    rolloverSessionId: `rollover-${index}`,
  };
}

function messages(count: number): ChatMessage[] {
  return Array.from({ length: count }, (_, index) => index % 2 === 0
    ? {
        id: `user-${index}`,
        role: "user" as const,
        text: `질문 ${index}`,
        asOf: "2026-07-18",
        status: "sent" as const,
      }
    : {
        id: `assistant-${index}`,
        role: "assistant" as const,
        requestId: `request-${index}`,
        status: "complete" as const,
        response,
      });
}

describe("chat titles", () => {
  it("uses the normalized first question and never replaces it on later turns", () => {
    const first = appendPendingTurn(createChatSession("chat-1"), pendingInput(1)).session;
    const second = appendPendingTurn(first, pendingInput(2)).session;

    expect(firstQuestionTitle("  첫 질문\n입니다  ")).toBe("첫 질문 입니다");
    expect(first.title).toBe("첫 질문 1 입니다");
    expect(second.title).toBe(first.title);
  });

  it("ellipsizes by Unicode characters without splitting an emoji", () => {
    expect(ellipsizeChatTitle("123456", 5)).toBe("1234…");
    expect(ellipsizeChatTitle("법령🔎검색", 4)).toBe("법령🔎…");
    expect(ellipsizeChatTitle("짧은 제목", 20)).toBe("짧은 제목");
    expect(() => ellipsizeChatTitle("제목", 0)).toThrow(RangeError);
  });
});

describe("token-budgeted context", () => {
  it("uses a conservative Korean-aware estimate", () => {
    expect(estimateTextTokens("법령 검색")).toBe(4);
    expect(estimateTextTokens("abcdef 1234")).toBe(4);
    expect(estimateTextTokens("허가? yes!")).toBe(5);
  });

  it("selects the most recent completed turns while preserving chronological order", () => {
    const current: ChatSession = {
      id: "chat-1",
      title: "기존 제목",
      messages: messages(6),
      contextMessageCount: 6,
    };
    const latestTurn = selectConversationContext(current, "현재 질문", 250);

    expect(latestTurn.currentQuestion).toBe("현재 질문");
    expect(latestTurn.turns.length).toBeGreaterThan(0);
    expect(latestTurn.turns.at(-1)?.question).toBe("질문 4");
    expect(latestTurn.estimatedInputTokens).toBeLessThanOrEqual(250);
    expect(latestTurn.rolledOver).toBe(true);
  });

  it("ignores pending, stopped, and failed assistant messages", () => {
    const current = createChatSession("chat-1");
    current.messages = [
      ...messages(2),
      { id: "u2", role: "user", text: "대기", asOf: "2026-07-18", status: "sent" },
      { id: "a2", role: "assistant", requestId: "r2", status: "pending" },
    ];

    expect(selectConversationContext(current, "현재", DEFAULT_INPUT_CONTEXT_TOKENS).turns)
      .toHaveLength(1);
  });

  it("starts a new chat when full completed context plus the current question exceeds budget", () => {
    const current: ChatSession = {
      id: "chat-full",
      title: "이전 대화",
      messages: messages(4),
      contextMessageCount: 4,
    };
    const result = appendPendingTurn(current, {
      ...pendingInput(5),
      inputTokenBudget: estimateTextTokens("첫 질문 5 입니다") + MESSAGE_TOKEN_OVERHEAD,
    });

    expect(result.rolledOver).toBe(true);
    expect(result.session.id).toBe("rollover-5");
    expect(result.session.rolloverNotice).toBe(CONTEXT_ROLLOVER_NOTICE);
    expect(result.session.messages[0]).toMatchObject({ role: "user", text: "첫 질문 5 입니다" });
  });

  it("keeps the current chat when all completed context fits", () => {
    const current: ChatSession = {
      id: "chat-1",
      title: "기존 제목",
      messages: messages(2),
      contextMessageCount: 2,
    };
    const result = appendPendingTurn(current, {
      ...pendingInput(3),
      inputTokenBudget: DEFAULT_INPUT_CONTEXT_TOKENS,
    });

    expect(result.rolledOver).toBe(false);
    expect(result.session.id).toBe("chat-1");
    expect(result.session.title).toBe("기존 제목");
  });

  it("rejects invalid budgets but still reports an oversized current question", () => {
    expect(() => selectConversationContext(createChatSession("chat"), "질문", 0))
      .toThrow(RangeError);
    const selection = selectConversationContext(createChatSession("chat"), "긴질문", 1);
    expect(selection.rolledOver).toBe(true);
    expect(selection.turns).toEqual([]);
  });
});

describe("pending assistant transitions", () => {
  it("completes only the matching pending request", () => {
    const pending = appendPendingTurn(createChatSession("chat-1"), pendingInput(1)).session;
    const stale = completePendingTurn(pending, "stale-request", response);
    const completed = completePendingTurn(pending, "request-1", response);

    expect(stale).toBe(pending);
    expect(completed.messages[1]).toMatchObject({ status: "complete", response });
    expect(completePendingTurn(completed, "request-1", response)).toBe(completed);
  });

  it("marks matching pending requests as stopped or failed and ignores stale updates", () => {
    const pending = appendPendingTurn(createChatSession("chat-1"), pendingInput(1)).session;
    const stopped = stopPendingTurn(pending, "request-1");
    const failed = failPendingTurn(pending, "request-1", "연결 오류");

    expect(stopped.messages[1]).toMatchObject({ status: "stopped" });
    expect(failed.messages[1]).toMatchObject({ status: "error", error: "연결 오류" });
    expect(failPendingTurn(stopped, "request-1", "늦은 오류")).toBe(stopped);
    expect(stopPendingTurn(pending, "stale-request")).toBe(pending);
  });
});
