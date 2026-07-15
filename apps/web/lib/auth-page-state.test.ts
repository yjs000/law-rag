import { describe, expect, it } from "vitest";
import { authEventAction, oauthRedirectMessage } from "../app/page";

describe("auth page state", () => {
  it("shows an actionable retry message for an OAuth error or cancellation", () => {
    expect(oauthRedirectMessage("?auth=error")).toContain("다시 시도");
    expect(oauthRedirectMessage("?next=%2F&auth=error&error=access_denied")).toContain("취소");
  });

  it("does not show a stale error for success, unknown, or absent callback state", () => {
    expect(oauthRedirectMessage("?auth=success")).toBeNull();
    expect(oauthRedirectMessage("?auth=unexpected")).toBeNull();
    expect(oauthRedirectMessage("")).toBeNull();
  });

  it("clears private workspace state when another tab signs out", () => {
    expect(authEventAction("SIGNED_OUT")).toBe("clear");
  });

  it("rehydrates account state for sign-in and user updates without reacting to token noise", () => {
    expect(authEventAction("SIGNED_IN")).toBe("hydrate");
    expect(authEventAction("USER_UPDATED")).toBe("hydrate");
    expect(authEventAction("TOKEN_REFRESHED")).toBe("ignore");
    expect(authEventAction("INITIAL_SESSION")).toBe("ignore");
  });
});
