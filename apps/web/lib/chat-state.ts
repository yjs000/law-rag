import type { QuestionResponse } from "./contracts";

export const MAX_CONTEXT_MESSAGES = 400;
export const DEFAULT_CHAT_TITLE_LENGTH = 40;
export const CONTEXT_ROLLOVER_NOTICE =
  "이전 대화가 400개 메시지에 도달해 새 대화를 시작했습니다.";

type MessageBase = {
  id: string;
};

export type UserChatMessage = MessageBase & {
  role: "user";
  text: string;
  asOf: string;
  status: "sent";
};

export type AssistantChatMessage = MessageBase & {
  role: "assistant";
  requestId: string;
  status: "pending" | "complete" | "stopped" | "error";
  response?: QuestionResponse;
  error?: string;
};

export type ChatMessage = UserChatMessage | AssistantChatMessage;

export type ChatSession = {
  id: string;
  title: string | null;
  messages: ChatMessage[];
  rolloverNotice?: string;
};

export type PendingTurnInput = {
  requestId: string;
  userMessageId: string;
  assistantMessageId: string;
  question: string;
  asOf: string;
  rolloverSessionId: string;
};

export type PendingTurnResult = {
  session: ChatSession;
  rolledOver: boolean;
};

export function createChatSession(id: string): ChatSession {
  return { id, title: null, messages: [] };
}

export function firstQuestionTitle(question: string): string {
  return question.trim().replace(/\s+/g, " ");
}

export function ellipsizeChatTitle(
  title: string,
  maxLength = DEFAULT_CHAT_TITLE_LENGTH,
): string {
  if (!Number.isInteger(maxLength) || maxLength < 1) {
    throw new RangeError("maxLength must be a positive integer");
  }
  const characters = Array.from(title);
  if (characters.length <= maxLength) return title;
  if (maxLength === 1) return "…";
  return `${characters.slice(0, maxLength - 1).join("").trimEnd()}…`;
}

export function appendPendingTurn(
  current: ChatSession,
  input: PendingTurnInput,
): PendingTurnResult {
  const rolledOver = current.messages.length + 2 > MAX_CONTEXT_MESSAGES;
  const base = rolledOver
    ? {
        ...createChatSession(input.rolloverSessionId),
        rolloverNotice: CONTEXT_ROLLOVER_NOTICE,
      }
    : current;
  const normalizedQuestion = firstQuestionTitle(input.question);
  const title = base.title ?? normalizedQuestion;
  const messages: ChatMessage[] = [
    ...base.messages,
    {
      id: input.userMessageId,
      role: "user",
      text: normalizedQuestion,
      asOf: input.asOf,
      status: "sent",
    },
    {
      id: input.assistantMessageId,
      role: "assistant",
      requestId: input.requestId,
      status: "pending",
    },
  ];
  return { session: { ...base, title, messages }, rolledOver };
}

export function completePendingTurn(
  session: ChatSession,
  requestId: string,
  response: QuestionResponse,
): ChatSession {
  return updatePendingAssistant(session, requestId, (message) => ({
    ...message,
    status: "complete",
    response,
  }));
}

export function stopPendingTurn(session: ChatSession, requestId: string): ChatSession {
  return updatePendingAssistant(session, requestId, (message) => ({
    ...message,
    status: "stopped",
  }));
}

export function failPendingTurn(
  session: ChatSession,
  requestId: string,
  error: string,
): ChatSession {
  return updatePendingAssistant(session, requestId, (message) => ({
    ...message,
    status: "error",
    error,
  }));
}

function updatePendingAssistant(
  session: ChatSession,
  requestId: string,
  update: (message: AssistantChatMessage) => AssistantChatMessage,
): ChatSession {
  const index = session.messages.findIndex(
    (message) =>
      message.role === "assistant"
      && message.requestId === requestId
      && message.status === "pending",
  );
  if (index < 0) return session;
  const messages = [...session.messages];
  messages[index] = update(messages[index] as AssistantChatMessage);
  return { ...session, messages };
}
