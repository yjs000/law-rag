import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const pageSource = readFileSync(new URL("./page.tsx", import.meta.url), "utf8");

describe("question submission busy notice", () => {
  it("maps the typed provider admission error to the existing alert banner", () => {
    expect(pageSource).toContain('cause instanceof ApiError && cause.code === "system_busy"');
    expect(pageSource).toContain("시스템이 바쁩니다. 잠시 후 다시 실행해 주세요.");
    expect(pageSource).toContain('className="error-banner" role="alert"');
  });

  it("uses only a backend public message for non-busy question failures", () => {
    const submitPath = pageSource.slice(
      pageSource.indexOf("const answer = await askQuestion"),
      pageSource.indexOf("function stopGeneration"),
    );

    expect(submitPath).toContain("cause.publicMessage");
    expect(submitPath).toContain("if (message)");
    expect(submitPath).toContain("stopPendingTurn(current, requestId)");
    expect(submitPath).not.toContain('cause instanceof Error ? cause.message : "연결 오류"');
  });
});
