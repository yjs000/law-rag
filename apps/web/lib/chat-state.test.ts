import { describe, expect, it } from "vitest";
import type { QuestionResponse } from "./contracts";
import {
  CONTEXT_ROLLOVER_NOTICE,
  MAX_CONTEXT_MESSAGES,
  appendPendingTurn,
  completePendingTurn,
  createChatSession,
  ellipsizeChatTitle,
  failPendingTurn,
  firstQuestionTitle,
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

describe("context rollover", () => {
  it("keeps a reserved request-response pair in a chat with 398 messages", () => {
    const current: ChatSession = {
      id: "chat-1",
      title: "기존 제목",
      messages: messages(MAX_CONTEXT_MESSAGES - 2),
      contextMessageCount: MAX_CONTEXT_MESSAGES - 2,
    };

    const result = appendPendingTurn(current, pendingInput(399));

    expect(result.rolledOver).toBe(false);
    expect(result.session.id).toBe("chat-1");
    expect(result.session.messages).toHaveLength(MAX_CONTEXT_MESSAGES);
    expect(result.session.title).toBe("기존 제목");
  });

  it("starts a new chat before the next turn when the current chat has 400 messages", () => {
    const current: ChatSession = {
      id: "chat-full",
      title: "이전 대화",
      messages: messages(MAX_CONTEXT_MESSAGES),
      contextMessageCount: MAX_CONTEXT_MESSAGES,
    };

    const result = appendPendingTurn(current, pendingInput(401));

    expect(result.rolledOver).toBe(true);
    expect(result.session.id).toBe("rollover-401");
    expect(result.session.rolloverNotice).toBe(CONTEXT_ROLLOVER_NOTICE);
    expect(result.session.messages).toHaveLength(2);
    expect(result.session.messages[0]).toMatchObject({
      role: "user",
      text: "첫 질문 401 입니다",
    });
    expect(result.session.title).toBe("첫 질문 401 입니다");
  });

  it("rolls over at 399 messages because a complete pair is reserved", () => {
    const current: ChatSession = {
      id: "chat-odd",
      title: "기존 대화",
      messages: messages(MAX_CONTEXT_MESSAGES - 1),
      contextMessageCount: MAX_CONTEXT_MESSAGES - 1,
    };

    expect(appendPendingTurn(current, pendingInput(400)).rolledOver).toBe(true);
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
