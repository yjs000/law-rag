import hashlib
import re
from datetime import date
from uuid import NAMESPACE_URL, uuid5

from defusedxml import ElementTree as ET

from app.domain.catalog import SourceKind
from app.domain.entities import LegalDocumentRecord, ProvisionRecord


class LawXmlParseError(ValueError):
    pass


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def element_text(element: ET.Element) -> str:
    return clean_text(" ".join(part for part in element.itertext() if part))


def first_text(root: ET.Element, *names: str) -> str | None:
    wanted = set(names)
    for node in root.iter():
        if local_name(node.tag) in wanted:
            text = element_text(node)
            if text:
                return text
    return None


def direct_text(root: ET.Element, *names: str) -> str | None:
    wanted = set(names)
    for node in list(root):
        if local_name(node.tag) in wanted:
            text = element_text(node)
            if text:
                return text
    return None


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    if len(digits) != 8:
        return None
    try:
        return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
    except ValueError:
        return None


def parse_search_results(xml: str, source_kind: SourceKind) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise LawXmlParseError("목록 XML을 파싱할 수 없습니다") from exc
    if local_name(root.tag) == "Response" and first_text(root, "result"):
        raise LawXmlParseError(f"Open API 오류 응답: {first_text(root, 'result')}")

    item_names = {"law"} if source_kind is SourceKind.LAW else {"admrul"}
    title_names = {"법령명한글", "법령명_한글"} if source_kind is SourceKind.LAW else {"행정규칙명"}
    results: list[dict[str, str]] = []
    for item in root.iter():
        if local_name(item.tag).lower() not in item_names:
            continue
        values: dict[str, str] = {}
        for node in item.iter():
            name = local_name(node.tag)
            text = element_text(node)
            if text:
                values[name] = text
        title = next((values[name] for name in title_names if values.get(name)), "")
        if not title:
            continue
        results.append(
            {
                "title": title,
                "id": values.get("법령ID", values.get("행정규칙ID", "")),
                "mst": values.get("법령일련번호", values.get("행정규칙일련번호", "")),
                "effective_date": values.get("시행일자", ""),
                "detail_link": values.get("법령상세링크", values.get("행정규칙상세링크", "")),
            }
        )
    return results


def parse_history_msts(xml: str) -> set[str]:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise LawXmlParseError("변경이력 XML을 파싱할 수 없습니다") from exc
    if local_name(root.tag) == "Response" and first_text(root, "result"):
        raise LawXmlParseError(f"Open API 오류 응답: {first_text(root, 'result')}")
    return {
        text
        for node in root.iter()
        if local_name(node.tag) == "법령일련번호" and (text := element_text(node))
    }


def _provision(
    *,
    namespace: str,
    path: str,
    heading: str | None,
    content: str,
    parent_path: str | None,
    ordinal: int,
) -> ProvisionRecord | None:
    content = clean_text(content)
    if not content:
        return None
    return ProvisionRecord(
        id=uuid5(NAMESPACE_URL, f"{namespace}#{path}"),
        path=path,
        heading=clean_text(heading) or None,
        content=content,
        parent_path=parent_path,
        ordinal=ordinal,
    )


def _parse_nested(
    article: ET.Element,
    namespace: str,
    article_path: str,
    start_ordinal: int,
) -> list[ProvisionRecord]:
    provisions: list[ProvisionRecord] = []
    ordinal = start_ordinal
    level_specs = (
        ("항", "항번호", "항내용", "항"),
        ("호", "호번호", "호내용", "호"),
        ("목", "목번호", "목내용", "목"),
    )
    parent_by_element: dict[int, str] = {id(article): article_path}
    for element in article.iter():
        tag = local_name(element.tag)
        match = next((spec for spec in level_specs if tag == spec[0]), None)
        if not match:
            continue
        _, number_tag, content_tag, label = match
        number = direct_text(element, number_tag) or str(len(provisions) + 1)
        content = direct_text(element, content_tag)
        if not content:
            continue
        parent = article
        for candidate in article.iter():
            if candidate is element:
                break
            if element in list(candidate):
                parent = candidate
        parent_path = parent_by_element.get(id(parent), article_path)
        path = f"{parent_path}/{label}{clean_text(number)}"
        record = _provision(
            namespace=namespace,
            path=path,
            heading=None,
            content=content,
            parent_path=parent_path,
            ordinal=ordinal,
        )
        if record:
            provisions.append(record)
            parent_by_element[id(element)] = path
            ordinal += 1
    return provisions


def parse_legal_document(
    xml: str,
    *,
    expected_title: str,
    source_kind: SourceKind,
    source_url: str,
    mst_override: str | None = None,
) -> LegalDocumentRecord:
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise LawXmlParseError("본문 XML을 파싱할 수 없습니다") from exc

    title = first_text(root, "법령명_한글", "법령명한글", "행정규칙명")
    if title != expected_title:
        raise LawXmlParseError(
            f"허용 목록 제목 불일치: expected={expected_title!r}, actual={title!r}"
        )

    source_id = first_text(root, "법령ID", "행정규칙ID") or ""
    mst = mst_override or first_text(root, "법령일련번호", "행정규칙일련번호") or source_id
    if not source_id or not mst:
        raise LawXmlParseError("법령 ID 또는 일련번호가 없습니다")

    namespace = f"{source_kind}:{source_id}:{mst}"
    provisions: list[ProvisionRecord] = []
    ordinal = 0
    article_nodes = [
        node
        for node in root.iter()
        if local_name(node.tag) == "조문단위" and first_text(node, "조문내용")
    ]
    if not article_nodes:
        article_nodes = [
            node
            for node in root.iter()
            if local_name(node.tag) == "조문" and first_text(node, "조문내용")
        ]
    for article in article_nodes:
        number = first_text(article, "조문번호") or str(ordinal + 1)
        branch = first_text(article, "조문가지번호")
        path = f"제{clean_text(number)}조"
        if branch and branch not in {"0", "00"}:
            path += f"의{clean_text(branch)}"
        record = _provision(
            namespace=namespace,
            path=path,
            heading=first_text(article, "조문제목"),
            content=first_text(article, "조문내용") or "",
            parent_path=None,
            ordinal=ordinal,
        )
        if record:
            provisions.append(record)
            ordinal += 1
            nested = _parse_nested(article, namespace, path, ordinal)
            provisions.extend(nested)
            ordinal += len(nested)

    if not provisions:
        body = first_text(root, "조문내용", "본문", "내용")
        record = _provision(
            namespace=namespace,
            path="본문",
            heading=title,
            content=body or "",
            parent_path=None,
            ordinal=0,
        )
        if record:
            provisions.append(record)

    if not provisions:
        raise LawXmlParseError("검색 가능한 조문 본문이 없습니다")

    return LegalDocumentRecord(
        source_id=source_id,
        mst=mst,
        title=title,
        source_kind=source_kind,
        promulgation_number=first_text(root, "공포번호", "발령번호"),
        promulgated_on=parse_date(first_text(root, "공포일자", "발령일자")),
        effective_from=parse_date(first_text(root, "시행일자")),
        ministry=first_text(root, "소관부처", "소관부처명"),
        source_url=source_url,
        raw_format="XML",
        raw_sha256=hashlib.sha256(xml.encode("utf-8")).hexdigest(),
        provisions=provisions,
    )
