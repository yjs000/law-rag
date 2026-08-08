import { describe, expect, it } from "vitest";
import { authEventAction, HYDRATE_THROTTLE_MS, nextAuthUser, oauthRedirectMessage, shouldHydrateNow } from "../app/page";
import type { MockUser } from "./contracts";

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

describe("hydrate throttle (0034)", () => {
  it("skips re-hydration within the throttle window unless forced", () => {
    const last = 1_000;
    expect(shouldHydrateNow(last, last + HYDRATE_THROTTLE_MS - 1, false)).toBe(false);
    expect(shouldHydrateNow(last, last + HYDRATE_THROTTLE_MS, false)).toBe(true);
    expect(shouldHydrateNow(last, last + 1, true)).toBe(true);
  });

  it("always allows the first hydration (mount) via force", () => {
    expect(shouldHydrateNow(0, 0, true)).toBe(true);
  });
});

describe("nextAuthUser (0034)", () => {
  const userA: MockUser = {
    id: "user-1",
    email: "a@example.com",
    display_name: "A",
    auth_provider: "google",
    created_at: "2026-07-14T00:00:00Z",
  };
  const userAUpdated: MockUser = { ...userA, display_name: "A renamed" };
  const userB: MockUser = { ...userA, id: "user-2" };

  it("keeps the same reference when the id is unchanged, so `user`-keyed effects don't refire", () => {
    expect(nextAuthUser(userA, userAUpdated)).toBe(userA);
  });

  it("swaps to the incoming user when the id changes or on sign-out/sign-in transitions", () => {
    expect(nextAuthUser(userA, userB)).toBe(userB);
    expect(nextAuthUser(null, userA)).toBe(userA);
    expect(nextAuthUser(userA, null)).toBe(null);
  });
});
