from __future__ import annotations

import subprocess
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts import check_roadmap, render_roadmap
from scripts.roadmap_registry import (
    PlanRecord,
    load_registry,
    roadmap_digest,
    roadmap_sections,
    validate_registry,
)


class RoadmapRegistryFixtures(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
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
                "## 구현",
                "본문은 첫 ## 뒤에 있어야 한다.",
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

    def _clear_plans(self) -> None:
        for directory in ("todo", "active", "completed"):
            for path in (self.root / "docs" / "exec-plans" / directory).glob("*.md"):
                path.unlink()

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

    def test_header_reader_does_not_materialize_disk_body(self) -> None:
        path = self._write_plan()
        baseline = load_registry(self.root)
        baseline_digest = roadmap_digest(baseline)
        body = "\n## 구현\n> 상태: `Broken`\n" + ("개인 본문\n" * 10000)
        path.write_text(path.read_text(encoding="utf-8") + body, encoding="utf-8")

        with patch("pathlib.Path.read_text", side_effect=AssertionError("full body read")):
            records = load_registry(self.root)

        self.assertEqual(records[0].status, "Todo")
        self.assertEqual(roadmap_digest(records), baseline_digest)
        self.assertEqual(self._errors(records), [])

    def test_header_reader_accepts_introductory_prose_after_the_title(self) -> None:
        path = self._write_plan()
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "# 로드맵 레지스트리 테스트\n\n## 구현",
                "# 로드맵 레지스트리 테스트\n\n짧은 개요입니다.\n\n## 구현",
            ),
            encoding="utf-8",
        )

        self.assertEqual(self._errors(load_registry(self.root)), [])

    def test_staged_header_reader_does_not_use_full_blob_git_show(self) -> None:
        path = self._write_plan()
        path.write_text(
            path.read_text(encoding="utf-8")
            + "\n> 상태: `Broken`\n"
            + ("개인 본문\n" * 10000),
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)

        real_run = subprocess.run

        def reject_full_blob(command: list[str], *args: object, **kwargs: object) -> object:
            if "show" in command:
                raise AssertionError("full git blob read")
            return real_run(command, *args, **kwargs)

        with patch("scripts.roadmap_registry.subprocess.run", side_effect=reject_full_blob):
            records = load_registry(self.root, staged=True)

        self.assertEqual(records[0].title, "로드맵 레지스트리 테스트")

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
                self.assertTrue(
                    any(
                        field in message and "python scripts/render_roadmap.py" in message
                        for message in messages
                    )
                )

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

    def test_staged_references_fail_closed_and_use_index_line_count(self) -> None:
        path = self._write_plan()
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)
        staged_text = path.read_text(encoding="utf-8").replace(
            "> - `apps/module.py` L1-L2 — 현재 동작 경계",
            "> - `apps/module.py` L1-L4 — 색인 파일 범위\n"
            "> - `worktree-only.py` L1-L1 — 색인에 없는 파일",
        )
        self.assertIn("worktree-only.py", staged_text)
        path.write_text(staged_text, encoding="utf-8")
        subprocess.run(["git", "add", str(path.relative_to(self.root))], cwd=self.root, check=True)
        (self.root / "apps" / "module.py").write_text("only worktree line\n", encoding="utf-8")
        (self.root / "worktree-only.py").write_text("worktree only\n", encoding="utf-8")

        records = load_registry(self.root, staged=True)
        errors = self._errors(records)

        self.assertTrue(any("worktree-only.py" in message and "존재" in message for message in errors))
        self.assertFalse(any("L4" in message and "넘습니다" in message for message in errors))

    def test_headerless_todo_and_active_are_actionable_but_completed_is_skipped(self) -> None:
        todo = self.root / "docs" / "exec-plans" / "todo" / "0001-headerless-todo.md"
        active = self.root / "docs" / "exec-plans" / "active" / "0002-headerless-active.md"
        completed = self.root / "docs" / "exec-plans" / "completed" / "0003-headerless-completed.md"
        todo.write_text("", encoding="utf-8")
        active.write_text("", encoding="utf-8")
        completed.write_text("", encoding="utf-8")

        records = load_registry(self.root)
        errors = self._errors(records)
        required_fields = {"작업 ID", "상태", "유형", "선행 조건", "다음 행동", "참고 범위"}

        self.assertEqual(
            {record.path.as_posix() for record in records},
            {
                "docs/exec-plans/todo/0001-headerless-todo.md",
                "docs/exec-plans/active/0002-headerless-active.md",
            },
        )
        for number in ("0001", "0002"):
            file_errors = [message for message in errors if number in message]
            for field in required_fields:
                self.assertTrue(any(field in message for message in file_errors), (number, field))
                self.assertTrue(
                    any(
                        field in message and "python scripts/render_roadmap.py" in message
                        for message in file_errors
                    ),
                    (number, field, file_errors),
                )
        self.assertFalse(any("0003-headerless-completed.md" in message for message in errors))

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

    def test_feature_subtask_ids_are_valid_and_remain_individually_unique(self) -> None:
        self._write_plan(number="0001", task_id="F-006-A", directory="active", status="Picked Up")
        self._write_plan(number="0002", task_id="F-006-B", directory="active", status="Blocked")
        self._write_plan(number="0003", task_id="F-006-A", directory="active", status="Blocked")

        errors = self._errors(load_registry(self.root))

        self.assertTrue(any("F-006-A" in message and "중복" in message for message in errors))
        self.assertFalse(any("F-006-B" in message and "형식" in message for message in errors))

    def test_picked_up_cardinality_is_one_actionable_global_error(self) -> None:
        self._write_plan(
            number="0001",
            directory="active",
            task_id="F-001",
            status="Picked Up",
            filename="0001-picked-one.md",
        )
        self._write_plan(
            number="0002",
            directory="active",
            task_id="F-002",
            status="Picked Up",
            filename="0002-picked-two.md",
        )

        errors = validate_registry(load_registry(self.root), self.root)

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0].field, "상태")
        self.assertIn("0개 또는 1개", errors[0].message)
        self.assertIn("F-001", str(errors[0]))
        self.assertIn("0001-picked-one.md", str(errors[0]))

    def test_all_forbidden_directory_status_pairs_are_rejected(self) -> None:
        pairs = [
            ("todo", "Picked Up"),
            ("todo", "Blocked"),
            ("todo", "Done"),
            ("active", "Done"),
            ("completed", "Todo"),
            ("completed", "Picked Up"),
            ("completed", "Blocked"),
        ]
        for index, (directory, status) in enumerate(pairs, start=1):
            with self.subTest(directory=directory, status=status):
                self._clear_plans()
                self._write_plan(
                    number=f"{index:04d}",
                    directory=directory,
                    status=status,
                    filename=f"{index:04d}-lifecycle.md",
                )
                errors = validate_registry(load_registry(self.root), self.root)
                lifecycle_errors = [error for error in errors if "lifecycle" in error.message]
                self.assertEqual(len(lifecycle_errors), 1)

    def test_next_action_sentence_rule_and_120_character_boundary(self) -> None:
        cases = [
            ("다음 행동을 기록하고 검증한다", False),
            ("첫 행동을 한다. 이어서 둘째 행동을 한다.", True),
            ("가" * 120, False),
        ]
        for index, (action, invalid) in enumerate(cases, start=1):
            with self.subTest(action=action):
                self._clear_plans()
                self._write_plan(number=f"{index:04d}", next_action=action)
                errors = validate_registry(load_registry(self.root), self.root)
                action_errors = [error for error in errors if error.field == "다음 행동"]
                self.assertEqual(bool(action_errors), invalid)

    def test_header_grammar_rejects_nonfinite_preamble_input(self) -> None:
        cases = {
            "prose-before-header": "설명부터 시작\n" + self._header(),
            "code-fence": self._header().replace(
                "\n# 로드맵 레지스트리 테스트", "\n```\n# 로드맵 레지스트리 테스트"
            ),
            "malformed-field": self._header().replace("> 상태: `Todo`", "> 상태 `Todo`"),
            "reference-outside-section": self._header().replace(
                "> 참고 범위:", "> - `apps/module.py` L1-L2 — 섹션 밖 범위\n> 참고 범위:"
            ),
            "unknown-field": self._header().replace("> 상태: `Todo`", "> 알 수 없는 필드: 값"),
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                self._clear_plans()
                path = self._write_plan()
                path.write_text(text, encoding="utf-8")
                errors = validate_registry(load_registry(self.root), self.root)
                self.assertTrue(
                    any(
                        error.field in {"색인 헤더", "참고 범위"}
                        or "허용되지 않은" in error.message
                        for error in errors
                    )
                )

    def test_public_models_expose_only_canonical_fields(self) -> None:
        self._write_plan()
        record = load_registry(self.root)[0]
        reference = record.references[0]

        for alias in ("plan_id", "numeric_id", "filename_id", "work_id", "type", "task_type", "file", "lifecycle"):
            self.assertFalse(hasattr(record, alias), alias)
        for alias in ("relative_path", "start", "end"):
            self.assertFalse(hasattr(reference, alias), alias)

    def test_registry_errors_expose_only_canonical_fields(self) -> None:
        self._write_plan(status="Running")
        error = next(
            error
            for error in validate_registry(load_registry(self.root), self.root)
            if error.field == "상태"
        )

        for alias in ("task_id", "path", "command", "fix"):
            self.assertFalse(hasattr(error, alias), alias)

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

    def test_sections_keep_picked_up_separate_and_digest_is_order_independent(self) -> None:
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
        self.assertEqual(list(sections), ["Picked Up", "Todo", "Blocked", "Done"])
        self.assertEqual([record.status for record in sections["Picked Up"]], ["Picked Up"])
        self.assertEqual(sections["Todo"], [])
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

    def test_rendering_valid_records_is_deterministic_and_has_only_index_fields(self) -> None:
        self._write_plan(
            number="0001",
            task_id="F-001",
            status="Todo",
            title="첫 번째 계획",
            filename="0001-first-plan.md",
        )
        self._write_plan(
            number="0002",
            directory="active",
            task_id="F-002",
            status="Picked Up",
            title="진행 중인 계획",
            filename="0002-picked-up.md",
        )
        self._write_plan(
            number="0003",
            directory="active",
            task_id="B-003",
            status="Blocked",
            plan_type="Bug",
            title="막힌 계획",
            filename="0003-blocked-plan.md",
        )
        self._write_plan(
            number="0004",
            directory="completed",
            task_id="D-004",
            status="Done",
            plan_type="Documentation",
            title="완료 계획",
            filename="0004-done-plan.md",
        )

        records = load_registry(self.root)
        rendered = render_roadmap.render_roadmap(records)

        self.assertEqual(rendered, render_roadmap.render_roadmap(list(reversed(records))))
        self.assertIn("python scripts/render_roadmap.py", rendered)
        self.assertIn(roadmap_digest(records), rendered)
        self.assertLess(rendered.index("## Picked Up"), rendered.index("## Todo"))
        self.assertLess(rendered.index("## Todo"), rendered.index("## Blocked"))
        self.assertLess(rendered.index("## Blocked"), rendered.index("## Done"))
        self.assertIn(
            "[F-002 · Feature — 진행 중인 계획](exec-plans/active/0002-picked-up.md) — "
            "다음 행동: 요구사항별 회귀 테스트부터 시작",
            rendered,
        )
        self.assertIn("## Picked Up", rendered)

        task_rows = [
            line
            for line in rendered.splitlines()
            if line.startswith("- [") and " · " in line
        ]
        self.assertEqual(len(task_rows), 4)
        for row in task_rows:
            self.assertIn(" · ", row)
            self.assertIn("](", row)
            self.assertNotIn("보조 라벨", row)
            self.assertNotIn("선행 조건", row)
            self.assertTrue("다음 행동:" in row or "재개 조건:" in row)

    def test_done_section_keeps_only_newest_twelve_records_and_completed_index(self) -> None:
        self._clear_plans()
        for index in range(1, 14):
            self._write_plan(
                number=f"{index:04d}",
                directory="completed",
                task_id=f"D-{index:03d}",
                status="Done",
                plan_type="Documentation",
                title=f"완료 계획 {index:02d}",
                filename=f"{index:04d}-done-{index:02d}.md",
            )

        rendered = render_roadmap.render_roadmap(load_registry(self.root))

        self.assertNotIn("D-001 · Documentation", rendered)
        for index in range(2, 14):
            self.assertIn(f"D-{index:03d} · Documentation", rendered)
        self.assertEqual(rendered.count("exec-plans/completed/README.md"), 1)
        done_body = rendered.split("## Done", 1)[1]
        self.assertEqual(sum(line.startswith("- [D-") for line in done_body.splitlines()), 12)

    def test_renderer_validates_before_replacing_roadmap(self) -> None:
        roadmap_path = self.root / "docs" / "ROADMAP.md"
        roadmap_path.write_bytes(b"existing roadmap\n")
        self._write_plan(status="Invalid")

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = render_roadmap.main(["--repo-root", str(self.root)])

        self.assertEqual(exit_code, 1)
        self.assertEqual(roadmap_path.read_bytes(), b"existing roadmap\n")
        self.assertIn("상태", stderr.getvalue())

    def test_renderer_cli_writes_the_rendered_utf8_bytes_without_newline_translation(self) -> None:
        self._write_plan()
        roadmap_path = self.root / "docs" / "ROADMAP.md"

        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            exit_code = render_roadmap.main(["--repo-root", str(self.root)])

        self.assertEqual(exit_code, 0)
        expected = render_roadmap.render_roadmap(load_registry(self.root)).encode("utf-8")
        self.assertEqual(roadmap_path.read_bytes(), expected)

    def test_checker_reports_first_manual_difference_without_writing(self) -> None:
        self._write_plan()
        roadmap_path = self.root / "docs" / "ROADMAP.md"
        roadmap_path.write_text(
            render_roadmap.render_roadmap(load_registry(self.root)), encoding="utf-8"
        )
        original = roadmap_path.read_bytes()
        roadmap_path.write_bytes(original.replace("Todo".encode(), "T0do".encode(), 1))
        edited = roadmap_path.read_bytes()

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = check_roadmap.main(["--repo-root", str(self.root)])

        self.assertEqual(exit_code, 1)
        self.assertEqual(roadmap_path.read_bytes(), edited)
        self.assertIn("첫 번째 차이", stderr.getvalue())
        self.assertIn("python scripts/render_roadmap.py", stderr.getvalue())

    def test_checker_staged_mode_uses_index_plan_and_roadmap_bytes(self) -> None:
        plan_path = self._write_plan(title="초기 버전")
        roadmap_path = self.root / "docs" / "ROADMAP.md"
        roadmap_path.write_text(
            render_roadmap.render_roadmap(load_registry(self.root)), encoding="utf-8"
        )
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "add", "."], cwd=self.root, check=True)

        plan_path.write_text(self._header(title="색인 버전"), encoding="utf-8")
        subprocess.run(["git", "add", str(plan_path.relative_to(self.root))], cwd=self.root, check=True)
        index_records = load_registry(self.root, staged=True)
        roadmap_path.write_text(
            render_roadmap.render_roadmap(index_records), encoding="utf-8"
        )
        subprocess.run(
            ["git", "add", str(roadmap_path.relative_to(self.root))],
            cwd=self.root,
            check=True,
        )

        plan_path.write_text(self._header(title="작업 트리 버전"), encoding="utf-8")
        roadmap_path.write_text("worktree-only roadmap\n", encoding="utf-8")
        worktree_plan = plan_path.read_bytes()

        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            exit_code = check_roadmap.main(
                ["--staged", "--repo-root", str(self.root)]
            )

        self.assertEqual(exit_code, 0, stderr.getvalue())
        self.assertIn("parsed plans: 1", stdout.getvalue())
        self.assertIn(roadmap_digest(index_records), stdout.getvalue())
        self.assertEqual(plan_path.read_bytes(), worktree_plan)
        self.assertEqual(roadmap_path.read_text(encoding="utf-8"), "worktree-only roadmap\n")


if __name__ == "__main__":
    unittest.main()
