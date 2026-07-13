from datetime import date
from pathlib import Path

import pytest

from law_rag_collector.history import (
    HistoryVersion,
    effective_periods,
    parse_history_json,
    parse_history_xml,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_json_and_xml_history_have_same_versions_and_effective_periods() -> None:
    json_versions = parse_history_json((FIXTURES / "history.json").read_text(encoding="utf-8"))
    xml_versions = parse_history_xml((FIXTURES / "history.xml").read_text(encoding="utf-8"))

    assert sorted(item.mst for item in json_versions) == ["1000", "1001"]
    assert sorted(item.mst for item in xml_versions) == ["1000", "1001"]
    periods = effective_periods(json_versions)
    assert periods[0].effective_from == date(2020, 2, 1)
    assert periods[0].effective_to == date(2026, 1, 31)
    assert periods[1].effective_to is None


def test_effective_periods_reject_missing_dates_and_preserve_same_day_versions() -> None:
    with pytest.raises(ValueError, match="시행일"):
        effective_periods([HistoryVersion("001", "1000", None)])
    periods = effective_periods(
        [
            HistoryVersion("001", "1000", date(2020, 1, 1)),
            HistoryVersion("001", "1001", date(2020, 1, 1)),
            HistoryVersion("001", "1002", date(2021, 1, 1)),
        ]
    )
    assert [item.effective_to for item in periods[:2]] == [
        date(2020, 12, 31),
        date(2020, 12, 31),
    ]
    assert periods[2].effective_to is None
