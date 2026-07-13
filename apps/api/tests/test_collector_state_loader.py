import json
from datetime import date
from pathlib import Path

import pytest

from app.adapters.memory_repository import MemoryLegalRepository


@pytest.mark.asyncio
async def test_collector_manifest_loads_and_applies_effective_range(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw" / "law" / "001"
    raw_dir.mkdir(parents=True)
    fixture = Path(__file__).parent / "fixtures" / "law.json"
    raw_path = raw_dir / "1001-2026-02-01.json"
    raw_path.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")
    manifest = {
        "documents": {
            "law:001:1001:2026-02-01": {
                "title": "전기사업법",
                "mst": "1001",
                "effective_from": "2026-02-01",
                "effective_to": "2026-12-31",
                "raw_format": "JSON",
                "raw_path": "raw/law/001/1001-2026-02-01.json",
                "source_url": "https://www.law.go.kr/DRF/lawService.do",
            }
        },
        "runs": [{"finished_at": "2026-07-13T12:00:00+00:00"}],
    }
    (tmp_path / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    repository = MemoryLegalRepository()

    loaded, errors = repository.load_collector_state(tmp_path)

    assert loaded == 1
    assert errors == []
    assert await repository.search("전기사업", date(2026, 7, 13), 10)
    assert await repository.search("전기사업", date(2027, 1, 1), 10) == []
