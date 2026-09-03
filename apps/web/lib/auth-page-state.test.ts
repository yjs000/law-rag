import { describe, expect, it } from "vitest";
import {
  authEventAction,
  clampAsOfDate,
  HYDRATE_THROTTLE_MS,
  koreaTodayIsoDate,
  millisecondsUntilNextKoreaMidnight,
  nextAuthUser,
  oauthRedirectMessage,
  shouldHydrateNow,
} from "../app/page";
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

  it("clears private workspace state when another tab signs out, regardless of session state", () => {
    expect(authEventAction("SIGNED_OUT", true)).toBe("clear");
    expect(authEventAction("SIGNED_OUT", false)).toBe("clear");
  });

  it("always rehydrates on a real user update, and ignores token/session noise", () => {
    expect(authEventAction("USER_UPDATED", true)).toBe("hydrate");
    expect(authEventAction("TOKEN_REFRESHED", true)).toBe("ignore");
    expect(authEventAction("INITIAL_SESSION", true)).toBe("ignore");
  });
});

describe("authEventAction SIGNED_IN dedup (0040)", () => {
  it("hydrates on the first SIGNED_IN after a sign-out, i.e. a real sign-in", () => {
    expect(authEventAction("SIGNED_IN", false)).toBe("hydrate");
  });

  it("ignores repeated SIGNED_IN noise from tab refocus while a session is already active", () => {
    expect(authEventAction("SIGNED_IN", true)).toBe("ignore");
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

describe("koreaTodayIsoDate (0035)", () => {
  it("returns the KST calendar date even when UTC has already rolled to the next day", () => {
    // 2026-08-08 23:30 UTC = 2026-08-09 08:30 KST
    const utcLateNight = new Date("2026-08-08T23:30:00Z");
    expect(koreaTodayIsoDate(utcLateNight)).toBe("2026-08-09");
  });

  it("returns the KST calendar date when UTC hasn't rolled over yet", () => {
    // 2026-08-08 10:00 UTC = 2026-08-08 19:00 KST
    const utcMorning = new Date("2026-08-08T10:00:00Z");
    expect(koreaTodayIsoDate(utcMorning)).toBe("2026-08-08");
  });
});

describe("millisecondsUntilNextKoreaMidnight (F-006)", () => {
  it("waits only until the next KST midnight", () => {
    // 2026-08-08 14:59:59 UTC = 2026-08-08 23:59:59 KST
    expect(millisecondsUntilNextKoreaMidnight(new Date("2026-08-08T14:59:59Z"))).toBe(1_000);
  });

  it("schedules a full Korean day just after KST midnight", () => {
    // 2026-08-08 15:00:00 UTC = 2026-08-09 00:00:00 KST
    expect(millisecondsUntilNextKoreaMidnight(new Date("2026-08-08T15:00:00Z"))).toBe(86_400_000);
  });
});

describe("clampAsOfDate (0035)", () => {
  const today = "2026-08-08";

  it("passes through a date on or before today", () => {
    expect(clampAsOfDate("2026-08-08", today)).toBe("2026-08-08");
    expect(clampAsOfDate("2026-01-01", today)).toBe("2026-01-01");
  });

  it("clamps a future date down to today", () => {
    expect(clampAsOfDate("2026-08-09", today)).toBe(today);
    expect(clampAsOfDate("2099-12-31", today)).toBe(today);
  });

  it("passes through an empty or malformed value unchanged", () => {
    expect(clampAsOfDate("", today)).toBe("");
    expect(clampAsOfDate("not-a-date", today)).toBe("not-a-date");
  });
});
