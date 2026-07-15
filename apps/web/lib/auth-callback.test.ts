import { describe, expect, it } from "vitest";

import { authErrorPath, callbackBaseUrl, safeAuthNextPath } from "./auth-callback";

describe("OAuth callback boundaries", () => {
  it("allows only internal relative paths after authentication", () => {
    expect(safeAuthNextPath("/questions?id=history-1")).toBe("/questions?id=history-1");
    expect(safeAuthNextPath(null)).toBe("/?auth=success");
    expect(safeAuthNextPath("https://evil.example/steal")).toBe("/?auth=success");
    expect(safeAuthNextPath("//evil.example/steal")).toBe("/?auth=success");
    expect(safeAuthNextPath("/\\evil.example/steal")).toBe("/?auth=success");
  });

  it("uses a valid configured site origin without accepting an unsafe scheme", () => {
    expect(callbackBaseUrl("https://preview.example", "https://law-rag-web.vercel.app/path"))
      .toBe("https://law-rag-web.vercel.app");
    expect(callbackBaseUrl("http://localhost:3000", "http://localhost:3000/path"))
      .toBe("http://localhost:3000");
    expect(callbackBaseUrl("https://law-rag-web.vercel.app", "http://localhost:3000"))
      .toBe("https://law-rag-web.vercel.app");
    expect(callbackBaseUrl("https://law-rag-web.vercel.app", "javascript:alert(1)"))
      .toBe("https://law-rag-web.vercel.app");
    expect(callbackBaseUrl("https://law-rag-web.vercel.app", "not a url"))
      .toBe("https://law-rag-web.vercel.app");
  });

  it("preserves only the safe cancellation reason", () => {
    expect(authErrorPath("access_denied")).toBe("/?auth=error&error=access_denied");
    expect(authErrorPath("server_error")).toBe("/?auth=error");
    expect(authErrorPath("https://evil.example")).toBe("/?auth=error");
  });
});
