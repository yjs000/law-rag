import hashlib
import json
import re
from dataclasses import dataclass

from law_rag_core.domain.catalog import SourceKind


class TextFixtureError(ValueError):
    """일반 텍스트를 기존 Open API 파서 입력으로 옮길 수 없을 때 발생한다."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class AdaptedTextFixture:
    payload: str
    expected_title: str
    source_kind: SourceKind
    mode: str
    chapter: str | None
    section: str | None
    removed_ui_lines: int


@dataclass(frozen=True, slots=True)
class _ArticleBlock:
    number: str
    branch: str | None
    heading: str
    content: str


_ARTICLE_HEADER = re.compile(
    r"^\s*제\s*(\d+)\s*조(?:의\s*(\d+))?\s*\(([^)\r\n]+)\)"
)
_CHAPTER_HEADER = re.compile(r"^\s*제\s*\d+\s*장(?:의\s*\d+)?\s+.+?\s*$")
_SECTION_HEADER = re.compile(r"^\s*제\s*\d+\s*절(?:의\s*\d+)?\s+.+?\s*$")
_UI_NOISE = "조문체계도버튼연혁"


def _normalized_lines(text: str) -> tuple[list[str], int]:
    lines: list[str] = []
    removed = 0
    for raw_line in text.lstrip("\ufeff").splitlines():
        line = raw_line.rstrip()
        if line.strip() == _UI_NOISE:
            removed += 1
            continue
        lines.append(line)
    return lines, removed


def _article_blocks(lines: list[str]) -> list[_ArticleBlock]:
    starts = [index for index, line in enumerate(lines) if _ARTICLE_HEADER.match(line)]
    blocks: list[_ArticleBlock] = []
    paths: set[str] = set()
    for position, start in enumerate(starts):
        match = _ARTICLE_HEADER.match(lines[start])
        assert match is not None
        end = starts[position + 1] if position + 1 < len(starts) else len(lines)
        number, branch, heading = match.groups()
        path = f"제{number}조" + (f"의{branch}" if branch else "")
        if path in paths:
            raise TextFixtureError("duplicate_article_path", f"중복 조문 경로입니다: {path}")
        paths.add(path)
        content = "\n".join(lines[start:end]).strip()
        blocks.append(
            _ArticleBlock(
                number=number,
                branch=branch,
                heading=heading.strip(),
                content=content,
            )
        )
    return blocks


def _article_payload(
    blocks: list[_ArticleBlock], *, title: str, input_sha256: str
) -> str:
    article_nodes = []
    for block in blocks:
        node = {
            "조문번호": block.number,
            "조문제목": block.heading,
            "조문내용": block.content,
        }
        if block.branch:
            node["조문가지번호"] = block.branch
        article_nodes.append(node)
    return json.dumps(
        {
            "법령서비스": {
                "법령명_한글": title,
                "법령ID": "experiment-a-text-fixture",
                "법령일련번호": input_sha256,
                "조문": {"조문단위": article_nodes},
            }
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _title_body_payload(lines: list[str], *, input_sha256: str) -> tuple[str, str]:
    nonempty = [line.strip() for line in lines if line.strip()]
    if len(nonempty) < 2:
        raise TextFixtureError("missing_body", "제목 뒤에 본문이 필요합니다")
    title = nonempty[0]
    body = "\n".join(nonempty[1:])
    return (
        json.dumps(
            {
                "AdmRulService": {
                    "행정규칙명": title,
                    "행정규칙ID": "experiment-a-title-body",
                    "행정규칙일련번호": input_sha256,
                    "조문내용": [body],
                }
            },
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        title,
    )


def adapt_text_fixture(
    text: str,
    *,
    document_title: str,
    input_sha256: str | None = None,
) -> AdaptedTextFixture:
    if not text.strip("\ufeff\r\n\t "):
        raise TextFixtureError("empty_input", "입력 텍스트가 비어 있습니다")
    digest = input_sha256 or hashlib.sha256(text.encode("utf-8")).hexdigest()
    lines, removed_ui_lines = _normalized_lines(text)
    chapter = next((line.strip() for line in lines if _CHAPTER_HEADER.match(line)), None)
    section = next((line.strip() for line in lines if _SECTION_HEADER.match(line)), None)
    blocks = _article_blocks(lines)
    if blocks:
        return AdaptedTextFixture(
            payload=_article_payload(blocks, title=document_title, input_sha256=digest),
            expected_title=document_title,
            source_kind=SourceKind.LAW,
            mode="articles",
            chapter=chapter,
            section=section,
            removed_ui_lines=removed_ui_lines,
        )

    payload, title = _title_body_payload(lines, input_sha256=digest)
    return AdaptedTextFixture(
        payload=payload,
        expected_title=title,
        source_kind=SourceKind.ADMIN_RULE,
        mode="title_body",
        chapter=chapter,
        section=section,
        removed_ui_lines=removed_ui_lines,
    )
