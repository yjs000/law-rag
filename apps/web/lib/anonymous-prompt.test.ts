import { describe, expect, it } from "vitest";
import { claimAnonymousLoginPrompt, LOGIN_PROMPT_KEY } from "./anonymous-prompt";

describe("anonymous login prompt", () => {
  it("is claimed only once per session", () => {
    const values = new Map<string, string>();
    const storage = {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
    };

    expect(claimAnonymousLoginPrompt(storage)).toBe(true);
    expect(values.get(LOGIN_PROMPT_KEY)).toBe("true");
    expect(claimAnonymousLoginPrompt(storage)).toBe(false);
  });
});
