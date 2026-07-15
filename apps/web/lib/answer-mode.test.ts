import { describe, expect, it } from "vitest";
import {
  isTerraAvailabilityFailure,
  isTerraUnavailable,
  resolveCorpusAnswerMode,
  resolveResponseAnswerMode,
  TERRA_FALLBACK_NOTICE,
} from "./answer-mode";

describe("answer mode synchronization", () => {
  it("keeps Terra selectable until the API explicitly reports it unavailable", () => {
    expect(isTerraUnavailable(null)).toBe(false);
    expect(isTerraUnavailable({ ai_available: true })).toBe(false);
    expect(isTerraUnavailable({ ai_available: false })).toBe(true);
  });

  it("disables Terra only for availability failures", () => {
    expect(isTerraAvailabilityFailure("ai_disabled")).toBe(true);
    expect(isTerraAvailabilityFailure("quota_exhausted")).toBe(true);
    expect(isTerraAvailabilityFailure("billing_or_quota_error")).toBe(true);
    expect(isTerraAvailabilityFailure("generation_error")).toBe(false);
    expect(isTerraAvailabilityFailure("no_evidence")).toBe(false);
    expect(isTerraAvailabilityFailure(undefined)).toBe(false);
  });

  it("starts with Terra when AI is available", () => {
    expect(resolveCorpusAnswerMode({ ai_available: true })).toEqual({
      preference: "terra",
      notice: null,
    });
  });

  it("announces and selects search-only when Terra is initially unavailable", () => {
    expect(resolveCorpusAnswerMode({ ai_available: false })).toEqual({
      preference: "search_only",
      notice: TERRA_FALLBACK_NOTICE,
    });
  });

  it("uses the fallback response reason to synchronize a failed Terra request", () => {
    expect(resolveResponseAnswerMode("terra", {
      mode: "search_only",
      requested_answer_mode: "terra",
      fallback_reason: "quota_exhausted",
    })).toEqual({
      preference: "search_only",
      notice: TERRA_FALLBACK_NOTICE,
    });
  });

  it("does not announce fallback for an explicit search-only request", () => {
    expect(resolveResponseAnswerMode("search_only", {
      mode: "search_only",
      requested_answer_mode: "search_only",
    })).toEqual({ preference: "search_only", notice: null });
  });

  it("detects a Terra fallback from a legacy API response without new fields", () => {
    expect(resolveResponseAnswerMode("terra", { mode: "search_only" })).toEqual({
      preference: "search_only",
      notice: TERRA_FALLBACK_NOTICE,
    });
  });
});
