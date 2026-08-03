import json
from pathlib import Path

from experiments.chunking.run import PARSER_NAME, main, run_cli


FIXTURE = (
    Path(__file__).parents[1] / "fixtures" / "electric-utility-act-chapter-2.txt"
)


def test_cli_creates_report_and_json_from_current_parser(tmp_path, capsys) -> None:
    report = tmp_path / "experiment-a.md"
    json_output = tmp_path / "experiment-a.json"

    exit_code = run_cli(
        [str(FIXTURE), "--report", str(report), "--json-output", str(json_output)]
    )

    captured = capsys.readouterr()
    payload = json.loads(json_output.read_text(encoding="utf-8"))
    markdown = report.read_text(encoding="utf-8")
    assert exit_code == 0
    assert captured.err == ""
    assert payload["chunk_count"] == 6
    assert payload["parser"]["function"] == PARSER_NAME
    assert payload["parser"]["schema_version"] == "2"
    assert "실제 청킹 함수" in markdown
    assert "제2장 전기사업" in markdown
    for chunk in payload["chunks"]:
        assert chunk["content"] in captured.out
        assert chunk["content"] in markdown


def test_failed_run_preserves_previous_success_outputs(tmp_path, capsys) -> None:
    invalid_input = tmp_path / "invalid.txt"
    invalid_input.write_text("제목만 있음", encoding="utf-8")
    report = tmp_path / "experiment-a.md"
    report.write_text("previous report", encoding="utf-8")
    json_output = tmp_path / "experiment-a.json"
    json_output.write_text("previous json", encoding="utf-8")

    exit_code = run_cli(
        [
            str(invalid_input),
            "--report",
            str(report),
            "--json-output",
            str(json_output),
        ]
    )

    error = json.loads(capsys.readouterr().err)
    assert exit_code == 2
    assert error["status"] == "error"
    assert error["code"] == "missing_body"
    assert report.read_text(encoding="utf-8") == "previous report"
    assert json_output.read_text(encoding="utf-8") == "previous json"


def test_non_utf8_input_returns_structured_error_without_outputs(tmp_path, capsys) -> None:
    invalid_input = tmp_path / "invalid.txt"
    invalid_input.write_bytes(b"\xff\xfe\xfa")
    report = tmp_path / "experiment-a.md"
    json_output = tmp_path / "experiment-a.json"

    exit_code = run_cli(
        [
            str(invalid_input),
            "--report",
            str(report),
            "--json-output",
            str(json_output),
        ]
    )

    error = json.loads(capsys.readouterr().err)
    assert exit_code == 2
    assert error["code"] == "invalid_utf8"
    assert not report.exists()
    assert not json_output.exists()


def test_report_and_json_cannot_share_the_same_path(tmp_path, capsys) -> None:
    output = tmp_path / "same-output"

    exit_code = run_cli(
        [str(FIXTURE), "--report", str(output), "--json-output", str(output)]
    )

    error = json.loads(capsys.readouterr().err)
    assert exit_code == 2
    assert error["code"] == "duplicate_output_path"
    assert not output.exists()


def test_main_configures_utf8_console_before_running(monkeypatch) -> None:
    configured: list[str] = []

    class Stream:
        def reconfigure(self, *, encoding: str) -> None:
            configured.append(encoding)

    monkeypatch.setattr("experiments.chunking.run.sys.stdout", Stream())
    monkeypatch.setattr("experiments.chunking.run.sys.stderr", Stream())
    monkeypatch.setattr("experiments.chunking.run.run_cli", lambda: 0)

    try:
        main()
    except SystemExit as exc:
        assert exc.code == 0

    assert configured == ["utf-8", "utf-8"]
