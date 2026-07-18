import hashlib
import json
import re
from collections.abc import Iterator
from datetime import date
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from law_rag_core.domain.catalog import SourceKind
from law_rag_core.domain.entities import LegalDocumentRecord, ProvisionRecord


class LawJsonParseError(ValueError):
    pass


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return _clean(" ".join(_clean(item) for item in value))
    if isinstance(value, dict):
        return _clean(value.get("content")) if "content" in value else ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _walk(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _value(node: dict[str, Any], *names: str) -> str | None:
    for name in names:
        if name in node:
            text = _clean(node[name])
            if text:
                return text
    return None


def _first(payload: Any, *names: str) -> str | None:
    return next((text for node in _walk(payload) if (text := _value(node, *names))), None)


def _date(value: str | None) -> date | None:
    digits = re.sub(r"\D", "", value or "")
    if len(digits) != 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:]))
    except ValueError:
        return None


_TECHNICAL_SECTION = re.compile(r"(?<![\d.])(\d+\.\d+)(?![\d.])\s*(?=[가-힣<])")


def _technical_standard_sections(content: str) -> list[tuple[str, str]]:
    """하나의 행정규칙 문자열에 붙은 기술기준 절을 번호별로 분리한다."""
    matches = list(_TECHNICAL_SECTION.finditer(content))
    if len(matches) < 2:
        return []
    sections: list[tuple[str, str]] = []
    prefix = content[: matches[0].start()].strip()
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        section = content[match.start() : end].strip()
        if index == 0 and prefix:
            section = f"{prefix} {section}"
        sections.append((f"기준{match.group(1)}", section))
    return sections


def load_json(body: str) -> Any:
    try:
        return json.loads(body.lstrip("\ufeff\r\n\t "))
    except json.JSONDecodeError as exc:
        raise LawJsonParseError("JSON 응답을 파싱할 수 없습니다") from exc


def parse_search_results(body: str, source_kind: SourceKind) -> list[dict[str, str]]:
    payload = load_json(body)
    if isinstance(payload, dict) and set(payload).issubset({"result", "msg"}):
        raise LawJsonParseError(f"Open API 오류 응답: {_clean(payload.get('result'))}")
    title_names = (
        ("법령명한글", "법령명_한글") if source_kind is SourceKind.LAW else ("행정규칙명",)
    )
    results: list[dict[str, str]] = []
    for node in _walk(payload):
        title = _value(node, *title_names)
        if not title:
            continue
        source_id = _value(node, "법령ID", "행정규칙ID") or ""
        mst = _value(node, "법령일련번호", "행정규칙일련번호") or ""
        if not source_id and not mst:
            continue
        results.append(
            {
                "title": title,
                "id": source_id,
                "mst": mst,
                "effective_date": _value(node, "시행일자") or "",
                "detail_link": _value(node, "법령상세링크", "행정규칙상세링크") or "",
            }
        )
    if not results:
        raise LawJsonParseError("검색 결과 스키마를 인식할 수 없습니다")
    return results


def parse_history_msts(body: str) -> set[str]:
    payload = load_json(body)
    if isinstance(payload, dict) and set(payload).issubset({"result", "msg"}):
        raise LawJsonParseError(f"Open API 오류 응답: {_clean(payload.get('result'))}")
    values = {
        value
        for node in _walk(payload)
        if (value := _value(node, "법령일련번호", "행정규칙일련번호"))
    }
    if not values:
        raise LawJsonParseError("변경이력 스키마를 인식할 수 없습니다")
    return values


def parse_legal_document(
    body: str,
    *,
    expected_title: str,
    source_kind: SourceKind,
    source_url: str,
    mst_override: str | None = None,
) -> LegalDocumentRecord:
    payload = load_json(body)
    title = _first(payload, "법령명_한글", "법령명한글", "행정규칙명")
    if title != expected_title:
        raise LawJsonParseError(
            f"허용 목록 제목 불일치: expected={expected_title!r}, actual={title!r}"
        )
    source_id = _first(payload, "법령ID", "행정규칙ID") or ""
    mst = mst_override or _first(payload, "법령일련번호", "행정규칙일련번호") or source_id
    if not source_id or not mst:
        raise LawJsonParseError("법령 ID 또는 일련번호가 없습니다")

    namespace = f"{source_kind}:{source_id}:{mst}"
    provisions: list[ProvisionRecord] = []

    def nodes(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, dict):
            return [value]
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    def add(path: str, content: str | None, parent: str | None, heading: str | None = None) -> None:
        if not content:
            return
        provisions.append(
            ProvisionRecord(
                id=uuid5(NAMESPACE_URL, f"{namespace}#{path}"),
                path=path,
                heading=heading,
                content=content,
                parent_path=parent,
                ordinal=len(provisions),
            )
        )

    article_nodes: list[dict[str, Any]] = []
    for node in _walk(payload):
        if "조문단위" in node:
            article_nodes = nodes(node["조문단위"])
            break

    recorded_articles: set[str] = set()
    for article in article_nodes:
        number = _value(article, "조문번호") or str(len(provisions) + 1)
        branch = _value(article, "조문가지번호")
        article_path = f"제{number}조"
        if branch and branch not in {"0", "00"}:
            article_path += f"의{branch}"
        if article_path not in recorded_articles:
            add(
                article_path,
                _value(article, "조문내용"),
                None,
                _value(article, "조문제목"),
            )
            recorded_articles.add(article_path)
        for paragraph in nodes(article.get("항")):
            paragraph_number = _value(paragraph, "항번호")
            paragraph_content = _value(paragraph, "항내용")
            paragraph_path = (
                f"{article_path}/항{paragraph_number}" if paragraph_number else article_path
            )
            if paragraph_number:
                add(paragraph_path, paragraph_content, article_path)
            item_parent = paragraph_path if paragraph_number else article_path
            for item in nodes(paragraph.get("호")):
                item_number = _value(item, "호번호") or str(len(provisions) + 1)
                item_path = f"{item_parent}/호{item_number}"
                add(item_path, _value(item, "호내용"), item_parent)
                for subitem in nodes(item.get("목")):
                    subitem_number = _value(subitem, "목번호") or str(len(provisions) + 1)
                    add(
                        f"{item_path}/목{subitem_number}",
                        _value(subitem, "목내용"),
                        item_path,
                    )
    if not provisions and isinstance(payload, dict):
        service = payload.get("AdmRulService")
        if isinstance(service, dict):
            raw_sections = service.get("조문내용", [])
            if not isinstance(raw_sections, list):
                raw_sections = [raw_sections]
            for index, raw_section in enumerate(raw_sections, 1):
                content = _clean(raw_section)
                technical_sections = _technical_standard_sections(content)
                if technical_sections:
                    for path, section_content in technical_sections:
                        add(path, section_content, None)
                    continue
                article_match = re.search(r"제\s*(\d+)\s*조(?:의\s*(\d+))?", content)
                path = f"본문/단락{index}"
                if article_match:
                    path = f"제{article_match.group(1)}조"
                    if article_match.group(2):
                        path += f"의{article_match.group(2)}"
                if any(item.path == path for item in provisions):
                    path = f"{path}/단락{index}"
                add(path, content, None)
    if not provisions:
        raise LawJsonParseError("검색 가능한 조문 본문이 없습니다")

    return LegalDocumentRecord(
        source_id=source_id,
        mst=mst,
        title=title,
        source_kind=source_kind,
        promulgation_number=_first(payload, "공포번호", "발령번호"),
        promulgated_on=_date(_first(payload, "공포일자", "발령일자")),
        effective_from=_date(_first(payload, "시행일자")),
        ministry=_first(payload, "소관부처", "소관부처명"),
        source_url=source_url,
        raw_format="JSON",
        raw_sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        provisions=provisions,
    )
