import hashlib
import json
import re
import unicodedata
from collections import Counter
from urllib.parse import urlparse

import pytest

from scripts.generate_layperson_energy_questions import (
    CORPUS_CATALOG,
    CORPUS_FINGERPRINT_SHA256,
    CURATED_QUESTION_OVERRIDES,
    DEFAULT_REVIEW,
    EXPECTED_COUNTS,
    SOURCES,
    _near_duplicate_pairs,
    build_bank,
    render_review,
)

OFFICIAL_SOURCE_REGISTRY = {
    "knrec_general_faq": ("https://www.knrec.or.kr/biz/faq/faq_list02.do?depth_1=&depth_2=&page=2"),
    "knrec_rps_faq": (
        "https://www.knrec.or.kr/biz/faq/faq_list02.do?"
        "depth_1=A030000&depth_2=A030300&depth_3=&page=2"
    ),
    "knrec_rec_process": (
        "https://www.knrec.or.kr/biz/introduce/new_rps/intro_cert_submit.do?gubun=C"
    ),
    "kepco_distributed_steps": (
        "https://cyber.kepco.co.kr/ckepco/mobile/resources/resources_step.jsp"
    ),
    "kepco_service_application": (
        "https://home.kepco.co.kr/kepco/front/html/CY/D/C/CYDCHP00102.html"
    ),
    "kepco_service_charter": ("https://home.kepco.co.kr/kepco/front/html/CY/H/A/CYHAHP001.html"),
    "kpx_faq": "https://kpx.or.kr/board.es?bid=0047&mid=a10504020000",
    "kesco_preuse_inspection": (
        "https://safety.kesco.or.kr/cyber/cr/ubi/moveUseBfeInspctStep01.do"
    ),
    "knrec_safety": (
        "https://www.knrec.or.kr/biz/introduce/new_policy/intro_energysafety.do?gubun=D"
    ),
    "knrec_fraud_relief": ("https://www.knrec.or.kr/biz/pds/notice/view.do?no=2581"),
    "ev_portal": "https://ev.or.kr/nportal/main.do",
    "ev_charger_guide_2026": "https://www.ev.or.kr/nportal/file/pdf/guideDownload.pdf",
    "energy_voucher_faq": ("https://www.energyv.or.kr/board/boardList.do?mstBoardId=44"),
    "motie_distributed_zone": ("https://www.motie.go.kr/kor/article/ATCLf724eb567/211968/view"),
    "law_solar_permit_interpretation": (
        "https://www.law.go.kr/DRF/lawService.do?"
        "ID=328431&OC=unicpla&mobileYn=Y&target=expc&type=HTML"
    ),
}

FORBIDDEN_CASE_FIELDS = {
    "answer",
    "answerable",
    "expected_documents",
    "expected_document_ids",
    "expected_evidence",
    "primary_evidence",
    "qrels",
    "reference",
    "reference_answer",
    "reference_contexts",
    "required_answer_facets",
}

LEGAL_TEMPLATE_PATTERN = re.compile(
    r"(?:"
    r"제\s*(?:몇|\d+)\s*(?:조|항|호|목)|"
    r"몇\s*조(?:에|에서|인지|인가|를|가)?|"
    r"조문|법조항|다음\s+각\s+(?:호|목)|"
    r"직접\s+정한\s+내용|규정에서|"
    r"전기사업법|전기안전관리법|분산에너지\s+활성화\s+특별법"
    r")"
)
EXPECTED_QUESTION_SET_SHA256 = "58be922c4bd9db7bce1360565da9b97de703e3b32c956c11e6a79285ee0b6b32"


@pytest.fixture(scope="module")
def bank() -> dict[str, object]:
    return build_bank()


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def test_bank_has_exactly_one_thousand_questions_with_expected_distributions(
    bank: dict[str, object],
) -> None:
    questions = bank["questions"]

    assert isinstance(questions, list)
    assert bank["question_count"] == 1000
    assert len(questions) == 1000
    assert bank["generation_method"] == {
        "scenario_count": 200,
        "question_facets_per_scenario": 5,
        "scenario_prompt_pairing": "manually_curated_compatible_groups",
        "wording": "newly_synthesized_not_verbatim_source_copy",
        "human_read_through_override_count": bank["static_audit"]["curated_override_count"],
    }
    assert Counter(str(case["intent"]) for case in questions) == EXPECTED_COUNTS
    assert bank["counts"]["intents"] == EXPECTED_COUNTS


def test_questions_are_not_annotated_and_contain_no_gold_answer_fields(
    bank: dict[str, object],
) -> None:
    contract = bank["annotation_contract"]
    questions = bank["questions"]

    assert contract == {
        "answers_included": False,
        "qrels_included": False,
        "expected_documents_included": False,
        "retrieval_experiment_executed": False,
    }
    assert bank["evaluation_readiness"]["retrieval_metrics_available"] is False
    assert bank["evaluation_readiness"]["planned_gold_artifact"] == (
        "experiment-d-lay-energy-gold-v1.json"
    )
    assert bank["corpus_context"] == {
        "as_of_date": "2026-08-03",
        "catalog_titles": list(CORPUS_CATALOG),
        "catalog_fingerprint_sha256": CORPUS_FINGERPRINT_SHA256,
        "scope_labels_assigned": False,
        "reason": "question approval must precede corpus coverage annotation",
    }
    assert isinstance(questions, list)
    for case in questions:
        assert case["evaluation_annotation_status"] == "not_annotated"
        assert case["source_origin"] == "source_inspired_synthetic"
        assert (
            case["question_sha256"] == hashlib.sha256(case["question"].encode("utf-8")).hexdigest()
        )
        assert FORBIDDEN_CASE_FIELDS.isdisjoint(case)
        assert "persona" not in case
        assert "journey_stage" not in case
        assert "scope_hint" not in case
        assert "research_source_ids" not in case

    expected_question_set_sha256 = hashlib.sha256(
        json.dumps(
            [{"id": case["id"], "question": case["question"]} for case in questions],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert bank["question_set_sha256"] == expected_question_set_sha256
    assert bank["question_set_sha256"] == EXPECTED_QUESTION_SET_SHA256
    assert bank["evaluation_readiness"]["answerability_values"] == [
        "fully_answerable",
        "partially_answerable",
        "clarification_required",
        "unanswerable",
    ]
    assert "insufficient_reason" in bank["evaluation_readiness"]["required_gold_fields"]


def test_every_question_only_references_registered_official_sources(
    bank: dict[str, object],
) -> None:
    registered_sources = bank["research"]["sources"]
    questions = bank["questions"]

    assert SOURCES == OFFICIAL_SOURCE_REGISTRY
    assert registered_sources == OFFICIAL_SOURCE_REGISTRY
    for url in registered_sources.values():
        parsed = urlparse(url)
        assert parsed.scheme == "https"
        assert parsed.hostname is not None
        assert parsed.hostname.endswith(
            (
                "knrec.or.kr",
                "kepco.co.kr",
                "kpx.or.kr",
                "kesco.or.kr",
                "ev.or.kr",
                "energyv.or.kr",
                "motie.go.kr",
                "law.go.kr",
            )
        )
    assert isinstance(questions, list)
    research_themes = bank["research"]["themes"]
    assert isinstance(research_themes, dict)
    for case in questions:
        theme = research_themes[case["research_theme_key"]]
        assert theme["mapping_granularity"] == "theme_not_individual_question"
        assert set(theme["source_ids"]) <= registered_sources.keys()


def test_questions_are_unique_nfkc_normalized_natural_korean_questions(
    bank: dict[str, object],
) -> None:
    questions = bank["questions"]
    assert isinstance(questions, list)

    normalized_questions: list[str] = []
    for case in questions:
        question = case["question"]
        assert isinstance(question, str)
        normalized = _normalize(question)
        normalized_questions.append(normalized)

        assert question == normalized
        assert 15 <= len(normalized) <= 120
        assert question.endswith("?")
        assert question.count("?") == 1
        assert re.search(r"[가-힣]", question)
        assert "\n" not in question
        assert "{" not in question and "}" not in question
        assert "TODO" not in question and "TBD" not in question
        assert LEGAL_TEMPLATE_PATTERN.search(question) is None

    assert len(set(normalized_questions)) == 1000
    assert _near_duplicate_pairs(questions) == []


def test_each_curated_scenario_has_five_distinct_question_facets(
    bank: dict[str, object],
) -> None:
    questions = bank["questions"]
    assert isinstance(questions, list)
    grouped: dict[str, list[dict[str, object]]] = {}
    for case in questions:
        grouped.setdefault(str(case["scenario_family_id"]), []).append(case)

    assert len(grouped) == 200
    for cases in grouped.values():
        assert len(cases) == 5
        assert len({str(case["question_style"]) for case in cases}) == 5
        assert len({str(case["intent"]) for case in cases}) == 1


def test_full_read_through_corrections_are_applied_by_stable_review_id(
    bank: dict[str, object],
) -> None:
    questions = bank["questions"]
    assert isinstance(questions, list)
    by_id = {str(case["id"]): str(case["question"]) for case in questions}

    assert set(CURATED_QUESTION_OVERRIDES) <= by_id.keys()
    for case_id, expected_question in CURATED_QUESTION_OVERRIDES.items():
        assert by_id[case_id] == expected_question

    for safety_case_id in (
        "lay-energy-0360",
        "lay-energy-0482",
        "lay-energy-0704",
        "lay-energy-0842",
        "lay-energy-0862",
        "lay-energy-0876",
        "lay-energy-0957",
    ):
        assert any(
            marker in by_id[safety_case_id]
            for marker in (
                "누가",
                "전문가",
                "직접 만지지 않고",
                "직접 전원을 끄지 말고",
            )
        )


def test_declared_static_audit_has_no_failures(bank: dict[str, object]) -> None:
    assert bank["static_audit"] == {
        "duplicate_count": 0,
        "global_near_duplicate_pair_count": 0,
        "forbidden_legal_citation_count": 0,
        "invalid_length_count": 0,
        "malformed_question_count": 0,
        "curated_override_count": bank["generation_method"]["human_read_through_override_count"],
    }


def test_review_contains_every_question_and_disclaims_search_and_gold_answers(
    bank: dict[str, object],
) -> None:
    review = render_review(bank)
    questions = bank["questions"]

    assert "정답·qrels 없음, 검색 실험 실행 안 함" in review
    assert "질문별 정답처럼 붙이지 않았다" in review
    assert "실제 평가셋으로 쓰려면" in review
    assert "Recall·MRR" in review
    assert isinstance(questions, list)
    for case in questions:
        assert review.count(f"| {case['id']} |") == 1


def test_outputs_cannot_overwrite_the_cancelled_v2_review() -> None:
    assert DEFAULT_REVIEW.name == "experiment-d-lay-energy-query-bank-v1.md"
    assert DEFAULT_REVIEW.name != "experiment-d-1000-review.md"
