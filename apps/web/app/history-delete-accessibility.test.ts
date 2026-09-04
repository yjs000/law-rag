import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("conversation deletion control", () => {
  it("keeps the delete control visible while a conversation has keyboard focus", () => {
    const css = readFileSync(new URL("./globals.css", import.meta.url), "utf8");

    expect(css).toContain(".history-item:hover .history-delete, .history-item:focus-within .history-delete, .history-delete:focus-visible { display: grid; place-items: center; }");
    expect(css).toContain(".history-delete:focus-visible { outline: 0; box-shadow: inset 0 0 0 2px var(--accent); }");
  });
});
