export type DialogKeyAction =
  | { type: "close" }
  | { type: "focus"; index: number }
  | { type: "none" };

export function dialogKeyAction(input: {
  key: string;
  shiftKey: boolean;
  activeIndex: number;
  controlCount: number;
}): DialogKeyAction {
  if (input.key === "Escape") return { type: "close" };
  if (input.key !== "Tab" || input.controlCount < 1) return { type: "none" };
  if (input.shiftKey && input.activeIndex <= 0) {
    return { type: "focus", index: input.controlCount - 1 };
  }
  if (!input.shiftKey && input.activeIndex >= input.controlCount - 1) {
    return { type: "focus", index: 0 };
  }
  return { type: "none" };
}

export function restoreFocus(target: Pick<HTMLElement, "focus"> | null): void {
  target?.focus();
}

export function focusInitial(target: Pick<HTMLElement, "focus"> | null): void {
  target?.focus();
}
