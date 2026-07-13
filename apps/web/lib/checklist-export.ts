import type { ChecklistItem } from "./contracts";

export type ExportFormat = "md" | "csv" | "pdf";

export type ChecklistExportInput = {
  question: string;
  asOfDate: string;
  projectStage: string;
  checklist: ChecklistItem[];
};

export function renderMarkdown(input: ChecklistExportInput): string {
  const lines = [
    "# 사업 단계 체크리스트",
    "",
    `- 질문: ${input.question}`,
    `- 법령 기준일: ${input.asOfDate}`,
    `- 사업 단계: ${input.projectStage}`,
    "",
  ];
  for (const item of input.checklist) {
    const citations = item.citation_ids.length ? ` (${item.citation_ids.join(", ")})` : "";
    lines.push(`- [ ] ${item.label}${citations}`);
  }
  return `${lines.join("\n")}\n`;
}

function csvCell(value: string): string {
  return `"${value.replaceAll('"', '""')}"`;
}

export function renderCsv(input: ChecklistExportInput): string {
  const rows = [
    ["질문", "법령 기준일", "사업 단계", "확인 항목", "상태", "인용"],
    ...input.checklist.map((item) => [
      input.question,
      input.asOfDate,
      input.projectStage,
      item.label,
      item.status,
      item.citation_ids.join("; "),
    ]),
  ];
  return `\uFEFF${rows.map((row) => row.map(csvCell).join(",")).join("\r\n")}\r\n`;
}

export function downloadText(filename: string, content: string, type: string): void {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
