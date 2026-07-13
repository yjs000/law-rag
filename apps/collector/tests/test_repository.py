from datetime import date
from uuid import NAMESPACE_URL, uuid5

from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord, ProvisionRecord

from law_rag_collector.client import RawResponse
from law_rag_collector.repository import MockCorpusRepository


def _document(raw_sha256: str = "sha") -> LegalDocumentRecord:
    return LegalDocumentRecord(
        source_id="001",
        mst="1000",
        title="전기사업법",
        source_kind=SourceKind.LAW,
        promulgation_number="제1호",
        promulgated_on=date(2020, 1, 1),
        effective_from=date(2020, 2, 1),
        ministry="산업통상자원부",
        source_url="https://example.test/lawService.do?OC=%5Bredacted%5D",
        raw_format="JSON",
        raw_sha256=raw_sha256,
        provisions=[
            ProvisionRecord(
                id=uuid5(NAMESPACE_URL, "test#1"),
                path="제1조",
                heading="목적",
                content="목적 조문",
            )
        ],
    )


def test_mock_repository_is_idempotent_and_reports_status(tmp_path) -> None:
    repository = MockCorpusRepository(tmp_path)
    raw = RawResponse("{}", "JSON", "https://example.test?OC=%5Bredacted%5D")

    assert repository.upsert(_document(), raw, effective_to=date(2025, 12, 31)) is True
    assert repository.upsert(_document(), raw, effective_to=date(2025, 12, 31)) is False

    status = repository.status()
    item = next(item for item in status["items"] if item["title"] == "전기사업법")
    assert status["documents"] == 1
    assert item["state"] == "ready"
    assert item["versions"] == 1
    assert "secret" not in (tmp_path / "manifest.json").read_text(encoding="utf-8")


def test_mock_repository_preserves_staged_effective_dates_for_same_mst(tmp_path) -> None:
    repository = MockCorpusRepository(tmp_path)
    raw = RawResponse("{}", "JSON", "https://example.test?OC=%5Bredacted%5D")
    first = _document("first")
    second = _document("second")
    second.effective_from = date(2020, 3, 1)

    repository.upsert(first, raw, effective_to=date(2020, 2, 29))
    repository.upsert(second, raw, effective_to=None)

    assert repository.status()["documents"] == 2
