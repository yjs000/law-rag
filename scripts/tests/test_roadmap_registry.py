from __future__ import annotations

import subprocess
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

from scripts.roadmap_registry import (
    PlanRecord,
    load_registry,
    roadmap_digest,
    roadmap_sections,
    validate_registry,
)


class RoadmapRegistryFixtures(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.root = Path(self.tempdir.name)
        (self.root / "docs" / "exec-plans" / "todo").mkdir(parents=True)
        (self.root / "docs" / "exec-plans" / "active").mkdir(parents=True)
        (self.root / "docs" / "exec-plans" / "completed").mkdir(parents=True)
        (self.root / "apps").mkdir()
        (self.root / "apps" / "module.py").write_text(
            "line one\nline two\nline three\nline four\n", encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _header(
        self,
        *,
        task_id: str = "F-001",
        status: str = "Todo",
        plan_type: str = "Feature",
        labels: str = "Data, Evaluation",
        prerequisites: str = "없음",
        next_action: str = "요구사항별 회귀 테스트부터 시작",
        references: list[str] | None = None,
        title: str = "로드맵 레지스트리 테스트",
    ) -> str:
        if references is None:
            references = [
                "- `apps/module.py` L1-L2 — 현재 동작 경계",
            ]
        return "\n".join(
            [
                f"> 작업 ID: `{task_id}`",
                f"> 상태: `{status}`",
                f"> 유형: `{plan_type}`",
                f"> 보조 라벨: {labels}",
                f"> 선행 조건: {prerequisites}",
                f"> 다음 행동: {next_action}",
                "> 참고 범위:",
                *[f"> {reference}" for reference in references],
                "",
                f"# {title}",
                "",
                "본문은 첫 ## 뒤에 있어야 한다.",
                "",
                "## 구현",
                "본문의 이 부분은 색인 파서가 읽지 않는다.",
                "",
            ]
        )

    def _write_plan(
        self,
        number: str = "0001",
        *,
        directory: str = "todo",
        filename: str | None = None,
        **kwargs: object,
    ) -> Path:
        plan_name = filename or f"{number}-roadmap-test.md"
        path = self.root / "docs" / "exec-plans" / directory / plan_name
        path.write_text(self._header(**kwargs), encoding="utf-8")
        return path

    def _errors(self, records: list[PlanRecord]) -> list[str]:
        return [str(error) for error in validate_registry(records, self.root)]

    def test_loads_immutable_record_and_stops_header_at_first_h2(self) -> None:
        self._write_plan()

        records = load_registry(self.root)

        self.assertEqual(len(records), 1)
        record = records[0]
        self.assertIsInstance(record, PlanRecord)
        self.assertEqual(record.plan_number, 1)
        self.assertEqual(record.task_id, "F-001")
        self.assertEqual(record.status, "Todo")
        self.assertEqual(record.plan_type, "Feature")
        self.assertEqual(record.labels, ("Data", "Evaluation"))
        self.assertEqual(record.title, "로드맵 레지스트리 테스트")
        self.assertEqual(record.path.as_posix(), "docs/exec-plans/todo/0001-roadmap-test.md")
        self.assertEqual(record.references[0].start_line, 1)
        self.assertEqual(record.references[0].end_line, 2)
        with self.assertRaises(FrozenInstanceError):
            record.status = "Done"  # type: ignore[misc]

    def test_missing_required_fields_report_record_file_and_field(self) -> None:
        required = {
            "작업 ID": "> 작업 ID: `F-001`",
            "상태": "> 상태: `Todo`",
            "유형": "> 유형: `Feature`",
            "선행 조건": "> 선행 조건: 없음",
            "다음 행동": "> 다음 행동: 요구사항별 회귀 테스트부터 시작",
            "참고 범위": "> 참고 범위:",
        }
        for field, line in required.items():
            with self.subTest(field=field):
                text = self._header()
                if field == "참고 범위":
                    text = text.replace(
                        "> 참고 범위:\n> - `apps/module.py` L1-L2 — 현재 동작 경계\n",
                        "",
                    )
                else:
                    text = text.replace(f"{line}\n", "")
                self._write_plan(filename=f"0001-missing-{field}.md")
                path = self.root / "docs" / "exec-plans" / "todo" / f"0001-missing-{field}.md"
                path.write_text(text, encoding="utf-8")

                messages = self._errors(load_registry(self.root))

                expected_id = "0001" if field == "작업 ID" else "F-001"
                self.assertTrue(any(expected_id in message for message in messages))
                self.assertTrue(
                    any(path.relative_to(self.root).as_posix() in message for message in messages)
                )
                self.assertTrue(any(field in message for message in messages))

                path.unlink()

    def test_missing_h1_and_multiple_h1_are_reported(self) -> None:
        path = self._write_plan()
        text = path.read_text(encoding="utf-8").replace("# 로드맵 레지스트리 테스트", "제목 없음")
        path.write_text(text, encoding="utf-8")
        errors = self._errors(load_registry(self.root))
        self.assertTrue(any("제목" in message for message in errors))

        path.write_text(
            self._header().replace("# 로드맵 레지스트리 테스트", "# 첫 제목\n# 두 번째 제목"),
            encoding="utf-8",
        )
        errors = self._errors(load_registry(self.root))
        self.assertTrue(any("H1" in message or "제목" in message for message in errors))

    def test_header_field_grammar_and_reference_limits(self) -> None:
        long_action = "가" * 121
        references = [
            "- `apps/module.py` L1-L1 — 첫 범위",
            "- `apps/module.py` L2-L2 — 둘째 범위",
            "- `apps/module.py` L3-L3 — 셋째 범위",
            "- `apps/module.py` L4-L4 — 넷째 범위",
        ]
        self._write_plan(next_action=long_action, references=references)
        errors = self._errors(load_registry(self.root))
        self.assertTrue(any("120" in message and "다음 행동" in message for message in errors))
        self.assertTrue(any("3" in message and "참고 범위" in message for message in errors))

    def test_reference_path_and_inclusive_line_bounds_are_checked(self) -> None:
        references = [
            "- `/outside.py` L1-L1 — 절대 경로",
            "- `missing.py` L1-L1 — 없는 파일",
            "- `apps/module.py` L0-L1 — 0번 줄",
            "- `apps/module.py` L3-L2 — 뒤집힌 범위",
            "- `apps/module.py` L1-L5 — 끝을 넘는 범위",
        ]
        self._write_plan(references=references)

        errors = self._errors(load_registry(self.root))

        self.assertTrue(any("절대" in message or "상대" in message for message in errors))
        self.assertTrue(any("missing.py" in message and "존재" in message for message in errors))
        self.assertTrue(
            any("L0" in message or ("1" in message and "줄" in message) for message in errors)
        )
        self.assertTrue(any("시작 줄" in message and "끝 줄" in message for message in errors))
        self.assertTrue(any("5" in message and "줄" in message for message in errors))

    def test_unknown_values_duplicate_ids_and_picked_up_cardinality(self) -> None:
        self._write_plan(
            number="0001",
            task_id="F-001",
            status="Running",
            labels="UnknownLabel",
            plan_type="UnknownType",
        )
        self._write_plan(number="0002", task_id="F-001", status="Picked Up")
        self._write_plan(number="0003", task_id="B-001", status="Picked Up")

        errors = self._errors(load_registry(self.root))

        self.assertTrue(any("알 수 없는 상태" in message or "상태" in message for message in errors))
        self.assertTrue(any("알 수 없는 유형" in message or "유형" in message for message in errors))
        self.assertTrue(any("UnknownLabel" in message and "보조 라벨" in message for message in errors))
        self.assertTrue(any("중복" in message and "작업 ID" in message for message in errors))
        self.assertTrue(any("Picked Up" in message for message in errors))

    def test_lifecycle_rejects_forbidden_directory_and_state_pairs(self) -> None:
        self._write_plan(directory="todo", status="Blocked", filename="0001-todo-blocked.md")
        self._write_plan(directory="active", status="Done", filename="0002-active-done.md")
        self._write_plan(directory="completed", status="Todo", filename="0003-completed-todo.md")

        errors = self._errors(load_registry(self.root))

        self.assertGreaterEqual(
            sum("lifecycle" in message or "위치" in message for message in errors), 3
        )
        for number in ("0001", "0002", "0003"):
            self.assertTrue(any(number in message for message in errors))

    def test_sections_place_picked_up_with_todo_and_digest_is_order_independent(self) -> None:
        self._write_plan(
            number="0002", task_id="F-002", status="Blocked", filename="0002-second.md"
        )
        self._write_plan(
            number="0001", task_id="F-001", status="Picked Up", filename="0001-first.md"
        )
        self._write_plan(
            number="0003",
            task_id="F-003",
            status="Done",
            directory="completed",
            filename="0003-third.md",
        )
        records = load_registry(self.root)

        sections = roadmap_sections(records)
        self.assertEqual(list(sections), ["Todo", "Blocked", "Done"])
        self.assertEqual([record.status for record in sections["Todo"]], ["Picked Up"])
        self.assertEqual([record.status for record in sections["Blocked"]], ["Blocked"])
        self.assertEqual([record.status for record in sections["Done"]], ["Done"])
        self.assertEqual(roadmap_digest(records), roadmap_digest(list(reversed(records))))
        self.assertNotEqual(roadmap_digest(records), roadmap_digest(records[:-1]))

    def test_staged_mode_reads_index_bytes_instead_of_worktree(self) -> None:
        path = self._write_plan()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)

        staged_text = path.read_text(encoding="utf-8").replace("로드맵 레지스트리 테스트", "색인 버전")
        path.write_text(staged_text, encoding="utf-8")
        subprocess.run(["git", "add", str(path.relative_to(self.root))], cwd=self.root, check=True)
        path.write_text(staged_text.replace("색인 버전", "작업 트리 버전"), encoding="utf-8")

        records = load_registry(self.root, staged=True)

        self.assertEqual(records[0].title, "색인 버전")


if __name__ == "__main__":
    unittest.main()
