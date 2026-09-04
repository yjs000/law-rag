import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "./api-client";
import {
  askQuestionWithRetry,
  GENERATION_ATTEMPT_TIMEOUT_MS,
  GENERATION_CANCEL_TIMEOUT_MS,
  GENERATION_MAX_ATTEMPTS,
  GENERATION_OVERALL_TIMEOUT_MS,
} from "./generation-retry";
import type { QuestionInput, QuestionResponse } from "./contracts";

const response: QuestionResponse = {
  mode: "ai",
  summary: "요약",
  scope: "범위",
  sections: [],
  checklist: [],
  citations: [],
  limitations: [],
};

function fallbackResponse(
  fallback_reason: NonNullable<QuestionResponse["fallback_reason"]>,
  overrides: Partial<QuestionResponse> = {},
): QuestionResponse {
  return {
    mode: "search_only",
    fallback_reason,
    summary: "검색 결과",
    scope: "범위",
    sections: [],
    checklist: [],
    citations: [],
    limitations: [],
    ...overrides,
  };
}

const input: QuestionInput = {
  client_request_id: "attempt-1",
  question: "질문",
  as_of_date: "2026-08-08",
  project_stage: "planning",
};

function abortError(): DOMException {
  return new DOMException("Aborted", "AbortError");
}

/** ask() that always rejects with our own attempt-timeout AbortError when its signal aborts. */
function timeoutAsk() {
  return vi.fn().mockImplementation((_input: QuestionInput, signal: AbortSignal) => {
    return new Promise<QuestionResponse>((_resolve, reject) => {
      signal.addEventListener("abort", () => reject(abortError()));
    });
  });
}

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe("askQuestionWithRetry", () => {
  it("returns the response immediately when the first attempt succeeds", async () => {
    const ask = vi.fn().mockResolvedValue(response);
    const cancel = vi.fn().mockResolvedValue({ cancelled: true });
    const outerSignal = new AbortController().signal;

    const result = await askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => "attempt-2",
      outerSignal,
    });

    expect(result).toBe(response);
    expect(ask).toHaveBeenCalledTimes(1);
    expect(cancel).not.toHaveBeenCalled();
  });

  it("cancels and retries with a fresh client_request_id after a per-attempt timeout", async () => {
    let calls = 0;
    const ask = vi.fn().mockImplementation((_input: QuestionInput, signal: AbortSignal) => {
      calls += 1;
      return new Promise<QuestionResponse>((resolve, reject) => {
        if (calls === 1) {
          signal.addEventListener("abort", () => reject(abortError()));
        } else {
          resolve(response);
        }
      });
    });
    const cancel = vi.fn().mockResolvedValue({ cancelled: true });
    const outerSignal = new AbortController().signal;

    const promise = askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => "attempt-2",
      outerSignal,
    });

    await vi.advanceTimersByTimeAsync(GENERATION_ATTEMPT_TIMEOUT_MS);
    const result = await promise;

    expect(result).toBe(response);
    expect(ask).toHaveBeenCalledTimes(2);
    expect(cancel).toHaveBeenCalledWith("attempt-1");
    expect(ask.mock.calls[1][0].client_request_id).toBe("attempt-2");
  });

  it("gives up after the max attempt count and throws the timeout error", async () => {
    const ask = timeoutAsk();
    const cancel = vi.fn().mockResolvedValue({ cancelled: true });
    const outerSignal = new AbortController().signal;
    let ids = 1;

    const promise = askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => `attempt-${++ids}`,
      outerSignal,
    });
    promise.catch(() => undefined); // keep unhandled-rejection warnings quiet while timers advance

    for (let i = 0; i < GENERATION_MAX_ATTEMPTS; i += 1) {
      await vi.advanceTimersByTimeAsync(GENERATION_ATTEMPT_TIMEOUT_MS);
    }

    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
    expect(ask).toHaveBeenCalledTimes(GENERATION_MAX_ATTEMPTS);
    expect(cancel).toHaveBeenCalledTimes(GENERATION_MAX_ATTEMPTS - 1);
  });

  it("does not retry a real server error - only timeouts are retried", async () => {
    const ask = vi.fn().mockRejectedValue(new Error("오늘의 계정 사용 한도를 초과했습니다."));
    const cancel = vi.fn();
    const outerSignal = new AbortController().signal;

    await expect(
      askQuestionWithRetry(input, { ask, cancel, nextClientRequestId: () => "attempt-2", outerSignal }),
    ).rejects.toThrow("오늘의 계정 사용 한도를 초과했습니다.");
    expect(ask).toHaveBeenCalledTimes(1);
    expect(cancel).not.toHaveBeenCalled();
  });

  it("propagates a user-initiated cancel (outer abort) without retrying", async () => {
    const controller = new AbortController();
    const ask = timeoutAsk();
    const cancel = vi.fn();

    const promise = askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => "attempt-2",
      outerSignal: controller.signal,
    });
    controller.abort();

    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
    expect(ask).toHaveBeenCalledTimes(1);
    expect(cancel).not.toHaveBeenCalled();
  });

  it("reports each new attempt id via onAttemptChange as it happens", async () => {
    let calls = 0;
    const ask = vi.fn().mockImplementation((_input: QuestionInput, signal: AbortSignal) => {
      calls += 1;
      return new Promise<QuestionResponse>((resolve, reject) => {
        if (calls === 1) signal.addEventListener("abort", () => reject(abortError()));
        else resolve(response);
      });
    });
    const onAttemptChange = vi.fn();

    const promise = askQuestionWithRetry(input, {
      ask,
      cancel: vi.fn().mockResolvedValue({ cancelled: true }),
      nextClientRequestId: () => "attempt-2",
      outerSignal: new AbortController().signal,
      onAttemptChange,
    });
    await vi.advanceTimersByTimeAsync(GENERATION_ATTEMPT_TIMEOUT_MS);
    await promise;

    expect(onAttemptChange.mock.calls.map((call) => call[0])).toEqual(["attempt-1", "attempt-2"]);
  });
});

describe("askQuestionWithRetry - generation_error fallback matrix (0045)", () => {
  it("retries a generation_error fallback with a fresh ID and returns the AI answer that follows", async () => {
    const fallback = fallbackResponse("generation_error");
    const ask = vi.fn()
      .mockResolvedValueOnce(fallback)
      .mockResolvedValueOnce(response);
    const cancel = vi.fn().mockResolvedValue({ cancelled: true });
    const onAttemptChange = vi.fn();

    const result = await askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => "attempt-2",
      outerSignal: new AbortController().signal,
      onAttemptChange,
    });

    expect(result).toBe(response);
    expect(ask).toHaveBeenCalledTimes(2);
    expect(ask.mock.calls[1][0].client_request_id).toBe("attempt-2");
    expect(onAttemptChange.mock.calls.map((call) => call[0])).toEqual(["attempt-1", "attempt-2"]);
    // The first attempt completed normally (it wasn't a timeout), so nothing needed cancelling.
    expect(cancel).not.toHaveBeenCalled();
  });

  it("returns the third fallback when all three attempts produce generation_error", async () => {
    const fallback1 = fallbackResponse("generation_error", { summary: "1차 검색 결과" });
    const fallback2 = fallbackResponse("generation_error", { summary: "2차 검색 결과" });
    const fallback3 = fallbackResponse("generation_error", { summary: "3차 검색 결과" });
    const ask = vi.fn()
      .mockResolvedValueOnce(fallback1)
      .mockResolvedValueOnce(fallback2)
      .mockResolvedValueOnce(fallback3);
    let ids = 1;

    const result = await askQuestionWithRetry(input, {
      ask,
      cancel: vi.fn().mockResolvedValue({ cancelled: true }),
      nextClientRequestId: () => `attempt-${++ids}`,
      outerSignal: new AbortController().signal,
    });

    expect(result).toBe(fallback3);
    expect(ask).toHaveBeenCalledTimes(3);
  });

  it("returns the stored fallback when a fallback is followed by two retryable failures", async () => {
    const fallback = fallbackResponse("generation_error");
    const ask = vi.fn()
      .mockResolvedValueOnce(fallback)
      .mockRejectedValueOnce(new ApiError("일시적으로 사용할 수 없습니다.", 503))
      .mockRejectedValueOnce(new ApiError("일시적으로 사용할 수 없습니다.", 502));

    const result = await askQuestionWithRetry(input, {
      ask,
      cancel: vi.fn().mockResolvedValue({ cancelled: true }),
      nextClientRequestId: () => "attempt-next",
      outerSignal: new AbortController().signal,
    });

    expect(result).toBe(fallback);
    expect(ask).toHaveBeenCalledTimes(3);
  });

  it("retries HTTP 502/503/504, but not the fallback-following attempts if AI succeeds", async () => {
    for (const status of [502, 503, 504]) {
      const ask = vi.fn()
        .mockRejectedValueOnce(new ApiError("서버 오류", status))
        .mockResolvedValueOnce(response);

      const result = await askQuestionWithRetry(input, {
        ask,
        cancel: vi.fn().mockResolvedValue({ cancelled: true }),
        nextClientRequestId: () => "attempt-2",
        outerSignal: new AbortController().signal,
      });

      expect(result).toBe(response);
      expect(ask).toHaveBeenCalledTimes(2);
    }
  });

  it("does not retry a provider admission busy response", async () => {
    const error = new ApiError("system_busy", 503, "system_busy");
    const ask = vi.fn().mockRejectedValue(error);
    const cancel = vi.fn();

    await expect(askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => "attempt-2",
      outerSignal: new AbortController().signal,
    })).rejects.toBe(error);
    expect(ask).toHaveBeenCalledTimes(1);
    expect(cancel).not.toHaveBeenCalled();
  });
  it("stops immediately on non-retryable HTTP statuses (400/401/402/409/429)", async () => {
    for (const status of [400, 401, 402, 409, 429]) {
      const error = new ApiError("재시도 불가 오류", status);
      const ask = vi.fn().mockRejectedValue(error);
      const cancel = vi.fn();

      await expect(
        askQuestionWithRetry(input, {
          ask,
          cancel,
          nextClientRequestId: () => "attempt-2",
          outerSignal: new AbortController().signal,
        }),
      ).rejects.toBe(error);
      expect(ask).toHaveBeenCalledTimes(1);
      expect(cancel).not.toHaveBeenCalled();
    }
  });

  it("returns non-generation_error fallbacks (grounding_failed, no_evidence, embedding_error, billing/quota) immediately without retrying", async () => {
    const reasons = [
      "grounding_failed",
      "no_evidence",
      "embedding_error",
      "billing_or_quota_error",
      "quota_exhausted",
      "ai_disabled",
    ] as const;

    for (const reason of reasons) {
      const fallback = fallbackResponse(reason);
      const ask = vi.fn().mockResolvedValue(fallback);
      const cancel = vi.fn();

      const result = await askQuestionWithRetry(input, {
        ask,
        cancel,
        nextClientRequestId: () => "attempt-2",
        outerSignal: new AbortController().signal,
      });

      expect(result).toBe(fallback);
      expect(ask).toHaveBeenCalledTimes(1);
      expect(cancel).not.toHaveBeenCalled();
    }
  });

  it("aborts an attempt at 55,000ms and starts the next attempt even when cancel() never settles", async () => {
    const ask = vi.fn()
      .mockImplementationOnce((_input: QuestionInput, signal: AbortSignal) => {
        return new Promise<QuestionResponse>((_resolve, reject) => {
          signal.addEventListener("abort", () => reject(abortError()));
        });
      })
      .mockResolvedValueOnce(response);
    const cancel = vi.fn().mockImplementation(() => new Promise(() => undefined)); // never settles

    const promise = askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => "attempt-2",
      outerSignal: new AbortController().signal,
    });

    await vi.advanceTimersByTimeAsync(GENERATION_ATTEMPT_TIMEOUT_MS);
    expect(ask).toHaveBeenCalledTimes(1);
    // cancel() never resolves; the bounded wait must still let the next attempt start.
    await vi.advanceTimersByTimeAsync(GENERATION_CANCEL_TIMEOUT_MS);
    const result = await promise;

    expect(result).toBe(response);
    expect(ask).toHaveBeenCalledTimes(2);
    expect(cancel).toHaveBeenCalledWith("attempt-1");
  });

  it("bounds the cancel wait to at most 1,000ms before starting the next attempt", async () => {
    const ask = vi.fn()
      .mockImplementationOnce((_input: QuestionInput, signal: AbortSignal) => {
        return new Promise<QuestionResponse>((_resolve, reject) => {
          signal.addEventListener("abort", () => reject(abortError()));
        });
      })
      .mockResolvedValueOnce(response);
    const cancel = vi.fn().mockImplementation(() => new Promise(() => undefined)); // never settles

    const promise = askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => "attempt-2",
      outerSignal: new AbortController().signal,
    });

    await vi.advanceTimersByTimeAsync(GENERATION_ATTEMPT_TIMEOUT_MS);
    // Just under the cancel bound: the next attempt must not have started yet.
    await vi.advanceTimersByTimeAsync(GENERATION_CANCEL_TIMEOUT_MS - 1);
    expect(ask).toHaveBeenCalledTimes(1);
    // Crossing the bound releases the wait and starts the next attempt.
    await vi.advanceTimersByTimeAsync(1);
    await promise;
    expect(ask).toHaveBeenCalledTimes(2);
  });

  it("stops issuing new attempts once the 170,000ms overall budget is exhausted", async () => {
    const ask = timeoutAsk();
    const cancel = vi.fn().mockResolvedValue({ cancelled: true });
    let ids = 1;

    const promise = askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => `attempt-${++ids}`,
      outerSignal: new AbortController().signal,
      maxAttempts: 10, // enough that only the overall budget - not the attempt count - stops the loop
    });
    promise.catch(() => undefined);

    // 3 full 55s attempts = 165,000ms elapsed. The 4th attempt starts
    // immediately once the 3rd aborts (retries don't wait for an extra
    // tick), so it has already been issued by the time this advance settles -
    // but with its timer capped to the 5,000ms remaining in the overall budget.
    await vi.advanceTimersByTimeAsync(GENERATION_ATTEMPT_TIMEOUT_MS);
    await vi.advanceTimersByTimeAsync(GENERATION_ATTEMPT_TIMEOUT_MS);
    await vi.advanceTimersByTimeAsync(GENERATION_ATTEMPT_TIMEOUT_MS);
    expect(ask).toHaveBeenCalledTimes(4);

    // Advancing by the remaining 5,000ms aborts the capped 4th attempt.
    await vi.advanceTimersByTimeAsync(GENERATION_OVERALL_TIMEOUT_MS - 3 * GENERATION_ATTEMPT_TIMEOUT_MS);
    expect(ask).toHaveBeenCalledTimes(4);

    // No 5th attempt: the overall budget is exhausted, even though attempts remain.
    await vi.advanceTimersByTimeAsync(GENERATION_ATTEMPT_TIMEOUT_MS);
    expect(ask).toHaveBeenCalledTimes(4);

    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
  });

  it("stops immediately on a user-initiated abort without retrying, even mid-attempt", async () => {
    const controller = new AbortController();
    const ask = timeoutAsk();
    const cancel = vi.fn();

    const promise = askQuestionWithRetry(input, {
      ask,
      cancel,
      nextClientRequestId: () => "attempt-2",
      outerSignal: controller.signal,
    });
    controller.abort();

    await expect(promise).rejects.toMatchObject({ name: "AbortError" });
    expect(ask).toHaveBeenCalledTimes(1);
    expect(cancel).not.toHaveBeenCalled();
  });
});
