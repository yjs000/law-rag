import csv
import io
from datetime import date
from uuid import uuid4

from app.application.checklist_exports import render_csv, render_markdown, render_pdf
from app.domain.schemas import (
    ChecklistDocument,
    ChecklistItem,
    Citation,
    ProjectStage,
)


def _document() -> ChecklistDocument:
    citation = Citation(
        id="C1",
        provision_id=uuid4(),
        document_title="전기사업법",
        version_label="MST 1",
        path="제1조제1항",
        quote="허가를 받아야 한다.",
        source_url="https://www.law.go.kr",
    )
    return ChecklistDocument(
        title="분산에너지 법령 체크리스트",
        as_of_date=date(2026, 7, 13),
        project_stage=ProjectStage.PERMITTING,
        items=[ChecklistItem(label="허가 확인", status="required", citation_ids=["C1"])],
        citations=[citation],
    )


def test_all_exports_preserve_canonical_item_citation_and_date() -> None:
    document = _document()
    markdown = render_markdown(document).decode()
    csv_text = render_csv(document).decode("utf-8-sig")
    pdf = render_pdf(document)

    assert "2026-07-13" in markdown
    assert "허가 확인" in markdown
    assert "C1" in markdown
    rows = list(csv.reader(io.StringIO(csv_text)))
    assert rows[1] == ["2026-07-13", "permitting", "required", "허가 확인", "C1"]
    assert rows[4][0] == "C1"
    assert pdf.startswith(b"%PDF-1.4")
    for value in ("2026-07-13", "허가 확인", "C1"):
        assert value.encode("utf-16-be").hex().upper().encode() in pdf


def test_export_contains_exact_legal_notice() -> None:
    notice = "이 서비스는 법률 자문을 대체하지 않습니다."
    assert notice in render_markdown(_document()).decode()
    assert notice.encode("utf-16-be").hex().upper().encode() in render_pdf(_document())
