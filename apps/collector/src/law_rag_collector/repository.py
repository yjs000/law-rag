import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from law_rag_core.domain.catalog import MVP_CATALOG
from law_rag_core.domain.entities import LegalDocumentRecord

from law_rag_collector.client import RawResponse


class MockCorpusRepository:
    """Supabase 연결 전 사용하는 원자적 파일 기반 목업 저장소."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.manifest_path = root / "manifest.json"

    def _read(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"schema_version": 1, "documents": {}, "runs": []}
        return json.loads(self.manifest_path.read_text(encoding="utf-8"))

    def _write(self, state: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        temporary = self.manifest_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(self.manifest_path)

    def upsert(
        self,
        document: LegalDocumentRecord,
        raw: RawResponse,
        *,
        effective_to: date | None,
    ) -> bool:
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
            / f"{document.mst}-{effective_key}.{raw.wire_format.lower()}"
        )
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if not unchanged or not raw_path.exists():
            raw_path.write_text(raw.body, encoding="utf-8")
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
            "items": items,
        }


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value else None
