import json
import os
import tempfile
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from law_rag_core.domain.catalog import MVP_CATALOG
from law_rag_core.domain.entities import LegalDocumentRecord

from law_rag_collector.activation import validate_for_activation
from law_rag_collector.client import RawResponse
from law_rag_collector.deletions import DeletionRecord


class MockCorpusRepository:
    """Supabase 연결 전 사용하는 원자적 파일 기반 목업 저장소."""

    def __init__(self, root: Path, *, today: Callable[[], date] = date.today) -> None:
        self.root = root
        self.manifest_path = root / "manifest.json"
        self._today = today

    def _read(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"schema_version": 1, "documents": {}, "runs": []}
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _write(self, state: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        content = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True)
        self._atomic_write(self.manifest_path, content)

    def _atomic_write(self, destination: Path, content: str) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=destination.parent,
                prefix=f".{destination.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
            temporary = None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def upsert(
        self,
        document: LegalDocumentRecord,
        raw: RawResponse,
        *,
        effective_to: date | None,
    ) -> bool:
        metadata = validate_for_activation(document, raw, today=self._today())
        state = self._read()
        effective_key = _iso(document.effective_from) or "unknown"
        key = f"{document.source_kind.value}:{document.source_id}:{document.mst}:{effective_key}"
        previous = state["documents"].get(key)
        unchanged = bool(previous and previous["raw_sha256"] == document.raw_sha256)
        raw_path = (
            self.root
            / "raw"
            / document.source_kind.value
            / document.source_id
            / f"{document.mst}-{effective_key}-{document.raw_sha256}.{raw.wire_format.lower()}"
        )
        if not raw_path.exists():
            self._atomic_write(raw_path, raw.body)
        state["documents"][key] = {
            "title": document.title,
            "source_kind": document.source_kind.value,
            "source_id": document.source_id,
            "mst": document.mst,
            "effective_from": _iso(document.effective_from),
            "effective_to": _iso(effective_to),
            "promulgated_on": _iso(document.promulgated_on),
            "raw_format": raw.wire_format,
            "raw_sha256": document.raw_sha256,
            "raw_path": str(raw_path.relative_to(self.root)).replace("\\", "/"),
            "source_url": raw.source_url,
            "fallback_reason": raw.fallback_reason,
            "lifecycle_state": metadata.lifecycle_state,
            "source_record_state": metadata.source_record_state,
            "has_supplementary_provisions": metadata.has_supplementary_provisions,
            "provision_count": len(document.provisions),
            "updated_at": datetime.now(UTC).isoformat(),
        }
        self._write(state)
        return not unchanged

    def record_run(self, command: str, results: list[dict[str, Any]]) -> None:
        state = self._read()
        state["runs"] = [
            *state.get("runs", [])[-49:],
            {
                "command": command,
                "finished_at": datetime.now(UTC).isoformat(),
                "ready": sum(item["state"] in {"ready", "unchanged"} for item in results),
                "failed": sum(item["state"] == "failed" for item in results),
                "failures": [item for item in results if item["state"] == "failed"],
            },
        ]
        self._write(state)

    def deletion_window(self, *, today: date) -> tuple[date, date]:
        """첫 실행은 8일, 이후에는 마지막 성공일 하루 전부터 겹쳐 조회한다."""
        state = self._read()
        completed = state.get("deletion_sync", {}).get("completed_on")
        if completed:
            completed_on = min(date.fromisoformat(completed), today)
            return completed_on - timedelta(days=1), today
        return today - timedelta(days=7), today

    def apply_source_deletions(
        self,
        records: list[DeletionRecord],
        *,
        completed_on: date,
    ) -> dict[str, dict[str, int]]:
        """Open API 레코드 삭제를 법적 폐지와 분리해 기록하고 체크포인트를 전진한다."""
        state = self._read()
        earliest: dict[tuple[str, str], date] = {}
        for record in records:
            key = (record.source_kind.value, record.mst)
            earliest[key] = min(earliest.get(key, record.deleted_on), record.deleted_on)
        stats = {
            "law": {"matched": 0, "changed": 0},
            "administrative_rule": {"matched": 0, "changed": 0},
        }
        for document in state["documents"].values():
            key = (document["source_kind"], document["mst"])
            deleted_on = earliest.get(key)
            if deleted_on is None:
                continue
            stats[key[0]]["matched"] += 1
            if (
                document.get("source_record_state") != "deleted"
                or document.get("source_deleted_on") != deleted_on.isoformat()
            ):
                document["source_record_state"] = "deleted"
                document["source_deleted_on"] = deleted_on.isoformat()
                document["updated_at"] = datetime.now(UTC).isoformat()
                stats[key[0]]["changed"] += 1
        state["deletion_sync"] = {
            "completed_on": completed_on.isoformat(),
            "record_count": len(records),
        }
        self._write(state)
        return stats

    def status(self) -> dict[str, Any]:
        state = self._read()
        documents = list(state["documents"].values())
        items = []
        for entry in MVP_CATALOG:
            versions = [item for item in documents if item["title"] == entry.title]
            items.append(
                {
                    "title": entry.title,
                    "source_kind": entry.source_kind.value,
                    "state": "ready" if versions else "missing",
                    "versions": len(versions),
                    "latest_effective_date": max(
                        (item["effective_from"] for item in versions if item["effective_from"]),
                        default=None,
                    ),
                }
            )
        return {
            "storage": "mock-file",
            "last_run": state.get("runs", [])[-1] if state.get("runs") else None,
            "documents": len(documents),
            "deletion_sync": state.get("deletion_sync"),
            "items": items,
        }


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None
