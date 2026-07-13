import pytest

from app.domain.catalog import SourceKind
from app.parsers.law_json import LawJsonParseError
from app.parsers.law_json import parse_search_results as parse_json
from app.parsers.law_xml import LawXmlParseError
from app.parsers.law_xml import parse_search_results as parse_xml


@pytest.mark.parametrize(
    "body,parser,error",
    [
        (
            '{"result":"사용자 정보 검증에 실패하였습니다.","msg":"IP 등록 필요"}',
            parse_json,
            LawJsonParseError,
        ),
        (
            "<Response><result>사용자 정보 검증에 실패하였습니다.</result>"
            "<msg>IP 등록 필요</msg></Response>",
            parse_xml,
            LawXmlParseError,
        ),
    ],
)
def test_open_api_error_is_not_treated_as_empty_search(body, parser, error) -> None:
    with pytest.raises(error, match="Open API 오류 응답"):
        parser(body, SourceKind.LAW)
