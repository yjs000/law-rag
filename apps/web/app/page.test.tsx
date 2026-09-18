import { readFileSync } from "node:fs";
import { afterEach, describe, expect, it, vi } from "vitest";

const reactHooks = vi.hoisted(() => ({ cursor: 0, initialQuestion: " \t\n " }));

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react");
  return {
    ...actual,
    useCallback: (callback: unknown) => callback,
    useEffect: () => undefined,
    useRef: (current: unknown) => ({ current }),
    useState: (initial: unknown) => {
      const index = reactHooks.cursor++;
      const value = index === 0
        ? reactHooks.initialQuestion
        : typeof initial === "function"
          ? (initial as () => unknown)()
          : initial;
      return [value, () => undefined];
    },
  };
});

import Home from "./page";

const pageSource = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("question submission busy notice", () => {
  it("maps the typed provider admission error to the existing alert banner", () => {
    expect(pageSource).toContain('cause instanceof ApiError && cause.code === "system_busy"');
    expect(pageSource).toContain("시스템이 바쁩니다. 잠시 후 다시 실행해 주세요.");
    expect(pageSource).toContain('className="error-banner" role="alert"');
  });

  it("uses the silent interruption transition only after a non-public question failure", () => {
    const submitPath = pageSource.slice(
      pageSource.indexOf("const answer = await askQuestion"),
      pageSource.indexOf("function stopGeneration"),
    );

    expect(submitPath).toContain("cause.publicMessage");
    expect(submitPath).toContain("if (message)");
    expect(submitPath).toContain("stopPendingTurn(current, requestId)");
    expect(submitPath).toMatch(
      /if \(message\) \{[\s\S]*failPendingTurn\(current, requestId, message\)[\s\S]*\} else \{\s*setActiveChat\(\(current\) => settleInterruptedPendingTurn\(current, requestId\)\);/,
    );
    expect(submitPath).not.toContain('cause instanceof Error ? cause.message : "연결 오류"');
  });
});

describe("question composer input boundary", () => {
  it("enables the send button for one non-whitespace character and keeps the UI cap", () => {
    expect(pageSource).toContain('disabled={question.trim().length === 0}');
    expect(pageSource).toContain('maxLength={2000}');
    expect(pageSource).not.toContain("question.trim().length < 2");
  });

  it("does not start the production request path for a whitespace-only submission", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    reactHooks.cursor = 0;
    const form = findElement(Home(), (node) => node.type === "form");
    expect(form).not.toBeNull();
    await form?.props.onSubmit?.({ preventDefault: vi.fn() });

    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("NVIDIA free-tier delay notice and finalize progress indicator", () => {
  it("shows the free-tier delay notice on the welcome screen", () => {
    expect(pageSource).toContain(
      "NVIDIA Nemotron 무료 티어 사용으로 답변 생성에 1분 이상 걸릴 수 있습니다.",
    );
  });

  it("pins a top finalize indicator only for the streaming assistant status, never exposing the internal stage name", () => {
    expect(pageSource).toContain("shouldShowFinalizeProgress");
    expect(pageSource).toContain('className="finalize-progress"');
    expect(pageSource).toContain('role="status"');
    expect(pageSource).not.toContain(">finalize<");
    expect(pageSource).not.toMatch(/finalize-progress[\s\S]{0,200}>finalize</);
  });

  it("removes the bottom finalize ellipsis by no longer passing pendingDetail to AnswerView", () => {
    expect(pageSource).not.toContain("pendingDetail=");
  });
});

type TestElement = {
  props: {
    children?: unknown;
    onSubmit?: (event: { preventDefault: () => void }) => unknown;
  };
  type: unknown;
};

function findElement(value: unknown, predicate: (node: TestElement) => boolean): TestElement | null {
  if (!value || typeof value !== "object") return null;
  const node = value as Partial<TestElement>;
  if (node.type !== undefined && node.props && predicate(node as TestElement)) return node as TestElement;
  const children = node.props?.children;
  if (Array.isArray(children)) {
    for (const child of children) {
      const match = findElement(child, predicate);
      if (match) return match;
    }
  }
  return findElement(children, predicate);
}
