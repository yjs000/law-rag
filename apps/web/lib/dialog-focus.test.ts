import { describe, expect, it, vi } from "vitest";
import { dialogKeyAction, focusInitial, restoreFocus } from "./dialog-focus";

describe("dialog keyboard focus", () => {
  it("wraps Tab and Shift+Tab inside the dialog", () => {
    expect(dialogKeyAction({ key: "Tab", shiftKey: false, activeIndex: 1, controlCount: 2 })).toEqual({ type: "focus", index: 0 });
    expect(dialogKeyAction({ key: "Tab", shiftKey: true, activeIndex: 0, controlCount: 2 })).toEqual({ type: "focus", index: 1 });
  });

  it("closes on Escape and ignores unrelated keys", () => {
    expect(dialogKeyAction({ key: "Escape", shiftKey: false, activeIndex: 0, controlCount: 2 })).toEqual({ type: "close" });
    expect(dialogKeyAction({ key: "Enter", shiftKey: false, activeIndex: 0, controlCount: 2 })).toEqual({ type: "none" });
  });

  it("returns focus to the control that opened the dialog", () => {
    const focus = vi.fn();
    restoreFocus({ focus });
    expect(focus).toHaveBeenCalledOnce();
  });

  it("puts initial focus on the Google login action", () => {
    const focus = vi.fn();
    focusInitial({ focus });
    expect(focus).toHaveBeenCalledOnce();
  });
});
