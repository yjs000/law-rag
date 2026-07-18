import type { QuestionResponse } from "./contracts";

/** Input budget only. The generation adapter must reserve output tokens separately. */
export const DEFAULT_INPUT_CONTEXT_TOKENS = 24_576;
/** Recommended output reserve; it is deliberately not subtracted from the input budget. */
export const RECOMMENDED_OUTPUT_TOKEN_RESERVE = 4_096;
export const MESSAGE_TOKEN_OVERHEAD = 8;
export const DEFAULT_CHAT_TITLE_LENGTH = 40;
export const CONTEXT_ROLLOVER_NOTICE =
  "이전 대화가 모델 입력 한도에 도달해 새 대화를 시작했습니다.";

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
  /** @deprecated Display-only compatibility counter; never used for context limits. */
  contextMessageCount: number;
  rolloverNotice?: string;
};

export type PendingTurnInput = {
  requestId: string;
  userMessageId: string;
  assistantMessageId: string;
  question: string;
  asOf: string;
  rolloverSessionId: string;
  inputTokenBudget?: number;
};

export type PendingTurnResult = {
  session: ChatSession;
  rolledOver: boolean;
};

export type ConversationContextTurn = {
  question: string;
  response: QuestionResponse;
};

export type ConversationContextSelection = {
  turns: ConversationContextTurn[];
  currentQuestion: string;
  estimatedInputTokens: number;
  rolledOver: boolean;
};

export function createChatSession(id: string): ChatSession {
  return { id, title: null, messages: [], contextMessageCount: 0 };
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
  const context = selectConversationContext(
    current,
    input.question,
    input.inputTokenBudget,
  );
  const rolledOver = context.rolledOver;
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
  return {
    session: {
      ...base,
      title,
      messages,
      contextMessageCount: base.contextMessageCount + 2,
    },
    rolledOver,
  };
}

/**
 * Conservatively estimates text tokens without binding the Web client to a model tokenizer.
 * Korean/CJK characters and punctuation count as one token each; compact ASCII words count
 * at one token per three characters. A fixed message overhead covers role/JSON framing.
 */
export function estimateTextTokens(text: string): number {
  let tokens = 0;
  let asciiRun = 0;
  const flushAscii = () => {
    if (asciiRun) tokens += Math.ceil(asciiRun / 3);
    asciiRun = 0;
  };
  for (const character of Array.from(text.normalize("NFKC"))) {
    if (/\s/u.test(character)) {
      flushAscii();
    } else if (/[A-Za-z0-9]/u.test(character)) {
      asciiRun += 1;
    } else {
      flushAscii();
      tokens += 1;
    }
  }
  flushAscii();
  return tokens;
}

export function selectConversationContext(
  session: ChatSession,
  currentQuestion: string,
  inputTokenBudget = DEFAULT_INPUT_CONTEXT_TOKENS,
): ConversationContextSelection {
  if (!Number.isInteger(inputTokenBudget) || inputTokenBudget < 1) {
    throw new RangeError("inputTokenBudget must be a positive integer");
  }
  const normalizedQuestion = firstQuestionTitle(currentQuestion);
  const currentTokens = estimateTextTokens(normalizedQuestion) + MESSAGE_TOKEN_OVERHEAD;
  const completedTurns = completedConversationTurns(session.messages);
  const turnCosts = completedTurns.map(estimateTurnTokens);
  const completeContextTokens = turnCosts.reduce((total, cost) => total + cost, currentTokens);
  const selected: ConversationContextTurn[] = [];
  let estimatedInputTokens = currentTokens;

  for (let index = completedTurns.length - 1; index >= 0; index -= 1) {
    const cost = turnCosts[index];
    if (estimatedInputTokens + cost > inputTokenBudget) break;
    selected.unshift(completedTurns[index]);
    estimatedInputTokens += cost;
  }

  return {
    turns: selected,
    currentQuestion: normalizedQuestion,
    estimatedInputTokens,
    rolledOver: completeContextTokens > inputTokenBudget,
  };
}

function completedConversationTurns(messages: ChatMessage[]): ConversationContextTurn[] {
  const turns: ConversationContextTurn[] = [];
  for (let index = 0; index < messages.length - 1; index += 1) {
    const user = messages[index];
    const assistant = messages[index + 1];
    if (
      user.role === "user"
      && assistant.role === "assistant"
      && assistant.status === "complete"
      && assistant.response
    ) {
      turns.push({ question: user.text, response: assistant.response });
      index += 1;
    }
  }
  return turns;
}

function estimateTurnTokens(turn: ConversationContextTurn): number {
  return estimateTextTokens(turn.question)
    + estimateTextTokens(JSON.stringify(turn.response))
    + (MESSAGE_TOKEN_OVERHEAD * 2);
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
