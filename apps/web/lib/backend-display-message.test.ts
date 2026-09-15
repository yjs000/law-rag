import { describe, expect, it } from "vitest";
import { backendDisplayMessage } from "./backend-display-message";

describe("backendDisplayMessage", () => {
  it.each([
    [{ message: "백엔드 메시지" }, "백엔드 메시지"],
    [{ detail: { message: "상세 메시지" } }, "상세 메시지"],
    [{ detail: "문자열 상세" }, "문자열 상세"],
    [{ detail: { code: "invalid_phase" } }, "invalid_phase"],
    [{ code: "invalid_request" }, "invalid_request"],
    [{ detail: {} }, null],
  ])("extracts only a backend-owned display value", (payload, expected) => {
    expect(backendDisplayMessage(payload)).toBe(expected);
  });
});
