import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const pageSource = readFileSync(new URL("../app/page.tsx", import.meta.url), "utf8");

describe("grounded QA frontend API boundary (F-006)", () => {
  it("does not preflight corpus status from the question UI", () => {
    expect(pageSource).not.toContain("getCorpusStatus");
    expect(pageSource).not.toContain("/v1/corpus/status");
  });

  it("keeps questions on the V2 execution client", () => {
    expect(pageSource).toContain("askQuestion");
    expect(pageSource).not.toContain('"/v1/questions"');
  });
});
