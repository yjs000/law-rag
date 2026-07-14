import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { SafeText } from "./safe-text";

describe("external string rendering", () => {
  it("escapes model and legal-source payloads instead of interpreting HTML", () => {
    const payload = '<img src=x onerror="alert(1)"><script>alert(2)</script>';
    const html = renderToStaticMarkup(<blockquote><SafeText>{payload}</SafeText></blockquote>);
    expect(html).not.toContain("<img");
    expect(html).not.toContain("<script");
    expect(html).toContain("&lt;img");
    expect(html).toContain("&lt;script&gt;");
  });
});
