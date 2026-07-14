import type { ReactNode } from "react";

/** Render external legal/model strings as React text nodes, never as HTML. */
export function SafeText({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
