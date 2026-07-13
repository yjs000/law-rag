from __future__ import annotations

import csv
import io
from collections.abc import Iterable

from app.domain.schemas import ChecklistDocument, ChecklistItem


def render_markdown(document: ChecklistDocument) -> bytes:
    lines = [
        f"# {document.title}",
        "",
        f"- 기준일: {document.as_of_date.isoformat()}",
        f"- 사업 단계: {document.project_stage.value}",
        "- 고지: 이 서비스는 법률 자문을 대체하지 않습니다.",
        "",
        "## 체크리스트",
        "",
    ]
    lines.extend(_markdown_item(item) for item in document.items)
    lines.extend(["", "## 인용", ""])
    lines.extend(
        f"- [{citation.id}] {citation.document_title} {citation.path} "
        f"({citation.version_label}): {citation.quote}"
        for citation in document.citations
    )
    return ("\n".join(lines) + "\n").encode()


def render_csv(document: ChecklistDocument) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["기준일", "사업 단계", "상태", "항목", "인용 ID"])
    for item in document.items:
        writer.writerow(
            [
                document.as_of_date.isoformat(),
                document.project_stage.value,
                item.status,
                item.label,
                " ".join(item.citation_ids),
            ]
        )
    writer.writerow([])
    writer.writerow(["인용 ID", "법령", "버전", "위치", "원문"])
    for citation in document.citations:
        writer.writerow(
            [
                citation.id,
                citation.document_title,
                citation.version_label,
                citation.path,
                citation.quote,
            ]
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def render_pdf(document: ChecklistDocument) -> bytes:
    """외부 PDF 엔진 없이 만드는 표지·브랜딩 없는 단순 텍스트 출력본."""
    lines = [
        document.title,
        f"기준일: {document.as_of_date.isoformat()}",
        f"사업 단계: {document.project_stage.value}",
        "이 서비스는 법률 자문을 대체하지 않습니다.",
        "",
        *(
            f"[{item.status}] {item.label} ({' '.join(item.citation_ids)})"
            for item in document.items
        ),
        "",
        *(f"[{c.id}] {c.document_title} {c.path}: {c.quote}" for c in document.citations),
    ]
    return _minimal_unicode_pdf(lines)


def _markdown_item(item: ChecklistItem) -> str:
    return f"- [{item.status}] {item.label} ({', '.join(item.citation_ids)})"


def _minimal_unicode_pdf(lines: Iterable[str]) -> bytes:
    commands = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
    for line in lines:
        encoded = line.encode("utf-16-be").hex().upper()
        commands.extend((f"<{encoded}> Tj", "T*"))
    commands.append("ET")
    stream = "\n".join(commands).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
        ),
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
        (
            b"<< /Type /Font /Subtype /Type0 /BaseFont /HYGoThic-Medium "
            b"/Encoding /UniKS-UCS2-H /DescendantFonts [6 0 R] >>"
        ),
        (
            b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /HYGoThic-Medium "
            b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Korea1) /Supplement 2 >> >>"
        ),
    ]
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode())
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(output)
