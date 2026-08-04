"""Render the fixed human approval review for the Experiment D question bank.

This command validates and renders question text only. It does not create answers,
qrels, retrieval candidates, scores, or search results, and it has no database or
embedding-provider dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path

from scripts.experiment_d_question_bank_provenance import (
    QUESTION_BANK_CONTEXT_CORPUS_SNAPSHOT_ID,
    QUESTION_BANK_CONTEXT_SUPPORTED_AS_OF_FROM,
    QUESTION_BANK_CONTEXT_SUPPORTED_AS_OF_THROUGH,
)
from scripts.experiment_d_question_identity import question_scope_set_sha256

REPOSITORY_ROOT = Path(__file__).parents[3]
DEFAULT_INPUT = (
    Path(__file__).parents[1] / "evaluation" / "experiment-d-lay-energy-query-bank-v1-draft.json"
)
DEFAULT_OUTPUT = (
    REPOSITORY_ROOT / "docs" / "generated" / "experiment-d-lay-energy-approval-review-v1.md"
)
FULL_REVIEW_LINK = "experiment-d-lay-energy-query-bank-v1.md"

BANK_VERSION = "experiment-d-lay-energy-query-bank-v1-draft"
BANK_STATUS = "draft_for_human_question_review"
QUESTION_STATUS = "not_annotated"
QUESTION_COUNT = 1000
SCENARIO_FAMILY_COUNT = 200
QUESTIONS_PER_FAMILY = 5
QUESTION_SET_SHA256 = "523325a6d86d2503492ff4dd8479f0a7e6045950dcef9288f970da0ae44d5a1a"
QUESTION_SCOPE_SET_SHA256 = "a8340555919ceac96616984d5f39b59ee9f0019c092a60918f772ffec4796845"
CATALOG_TITLE_SET_SHA256 = "c45f415a53f2390157f2c896c099ef57451fc046b2099f0bf94bee81d74cf006"
CATALOG_TITLES = (
    "전기사업법",
    "전기사업법 시행령",
    "전기사업법 시행규칙",
    "분산에너지 활성화 특별법",
    "분산에너지 활성화 특별법 시행령",
    "신에너지 및 재생에너지 개발ㆍ이용ㆍ보급 촉진법",
    "전기안전관리법",
    "전기저장시설의 화재안전성능기준(NFPC 607)",
    "전기저장시설의 화재안전기술기준(NFTC 607)",
)

REPRESENTATIVE_IDS = (
    "lay-energy-0001",
    "lay-energy-0111",
    "lay-energy-0201",
    "lay-energy-0291",
    "lay-energy-0381",
    "lay-energy-0441",
    "lay-energy-0511",
    "lay-energy-0601",
    "lay-energy-0671",
    "lay-energy-0741",
    "lay-energy-0796",
    "lay-energy-0846",
    "lay-energy-0881",
    "lay-energy-0921",
    "lay-energy-0961",
)

BROAD_OR_MISSING_FACTS = (
    (
        "lay-energy-0001",
        "허가·부지·계통·검사·판매까지 여러 필수 답변 요소를 포함할 수 있어 답의 경계가 넓다.",
    ),
    (
        "lay-energy-0002",
        "부지 확인부터 전기 판매까지 사업 생애주기 전체를 한 질문에서 요구한다.",
    ),
    (
        "lay-energy-0084",
        "비용·절감액·판매수익 비교에는 설비 규모, 사용량, 가격과 금융조건이 더 필요하다.",
    ),
    (
        "lay-energy-0101",
        "첫 상담기관은 지역, 용량, 자가사용·판매 여부와 사업 단계에 따라 달라질 수 있다.",
    ),
    (
        "lay-energy-0111",
        "소재지, 지목, 용도지역과 면적이 없어 특정 부지의 가능 여부를 확정할 수 없다.",
    ),
    (
        "lay-energy-0116",
        "농지 종류, 농업인 여부, 소재지와 용도지역이 없어 토지 이용 판단이 달라질 수 있다.",
    ),
    (
        "lay-energy-0171",
        "보호구역의 종류, 정확한 위치와 이격거리가 없어 적용 절차를 특정하기 어렵다.",
    ),
    (
        "lay-energy-0201",
        "발전원, 용량, 자가사용·판매 방식과 신청 주체에 따라 허가·신고가 달라질 수 있다.",
    ),
    (
        "lay-energy-0251",
        "‘소규모’의 실제 용량과 전기 사용 방식이 제시되지 않았다.",
    ),
    (
        "lay-energy-0291",
        "연결 가능성은 발전소 위치, 출력, 접속점과 현재 계통 여유 정보가 필요하다.",
    ),
    (
        "lay-energy-0441",
        "검사 종류와 시점은 설비 종류, 전압·용량과 공사 범위에 따라 달라질 수 있다.",
    ),
    (
        "lay-energy-0741",
        "지붕 구조·면적·방향·그늘, 지역과 전기사용량이 없어 가능성과 발전량을 판단하기 어렵다.",
    ),
    (
        "lay-energy-0846",
        "배터리 종류·용량, 실내외 설치와 기존 설비 변경 범위가 제시되지 않았다.",
    ),
    (
        "lay-energy-0961",
        "풍황 실측, 필지, 설비 규모, 계통과 환경 조건이 없어 사업 가능성을 확정할 수 없다.",
    ),
)

TIME_OR_LIVE_DATA = (
    (
        "lay-energy-0351",
        "현재 대기 순서와 예상 연결 시점은 법령 원문이 아니라 전력회사의 실시간 사업 데이터다.",
    ),
    (
        "lay-energy-0550",
        "최신 시장가격과 계약조건은 기준일 및 당시 시장·계약 자료가 필요하다.",
    ),
    (
        "lay-energy-0605",
        "올해 예산과 세부 조건은 법률보다 해당 연도의 지원사업 공고가 직접 근거다.",
    ),
    (
        "lay-energy-0641",
        "예산 소진과 대기접수 가능 여부는 해당 사업의 현재 운영 상태다.",
    ),
    (
        "lay-energy-0646",
        "신청일, 적용 공고와 경과규정이 없어 어느 연도 조건인지 확정하기 어렵다.",
    ),
    (
        "lay-energy-0731",
        "바우처 잔액과 사용기한은 기준일과 본인 인증이 필요한 개인 계정 데이터다.",
    ),
    (
        "lay-energy-0800",
        "충전기 설치비와 지원조건은 연도, 지자체와 사업 공고에 따라 바뀐다.",
    ),
    (
        "lay-energy-0836",
        "고장 상태와 복구 예정 시간은 충전기 운영사의 실시간 운영 데이터다.",
    ),
)

OUTSIDE_CORPUS = (
    (
        "lay-energy-0381",
        "시공업체 자격은 전기공사업 관련 법령, 실적은 업체 등록·실적 자료가 핵심이다.",
    ),
    (
        "lay-energy-0671",
        "신규 전기사용 신청 순서는 전력회사 공급약관과 업무 절차에 주로 의존한다.",
    ),
    (
        "lay-energy-0726",
        "에너지바우처 대상과 이용조건은 현재 9종 corpus 밖의 사업 법령·공고가 필요하다.",
    ),
    (
        "lay-energy-0756",
        "무료 설치와 절감 보장은 소비자계약 및 실제 제안서 검토가 핵심이다.",
    ),
    (
        "lay-energy-0766",
        "계약금 편취 대응은 민사·소비자·형사 영역이며 현재 9종 corpus에 직접 근거가 없다.",
    ),
    (
        "lay-energy-0796",
        "공동주택 동의와 주차장·건축·충전시설 규정은 현재 9종 corpus 밖 근거가 필요하다.",
    ),
    (
        "lay-energy-0826",
        "충전카드 계정과 사용내역은 충전사업자 시스템의 개인 데이터다.",
    ),
    (
        "lay-energy-0881",
        "분산에너지법 일부 외에도 지역 지정 여부와 실제 등록·거래계약 정보가 필요할 수 있다.",
    ),
    (
        "lay-energy-0911",
        "재생전기 구매상품과 계약은 시장 운영규칙 및 현재 상품정보가 필요할 수 있다.",
    ),
    (
        "lay-energy-0921",
        "특정 발전소의 사업 내용과 예상 영향은 해당 사업계획·영향 자료가 필요하다.",
    ),
    (
        "lay-energy-0926",
        "풍력 소음·그림자는 환경·입지 규정과 해당 사업의 영향자료가 핵심이다.",
    ),
    (
        "lay-energy-0956",
        "패널과 발전설비의 철거·폐기는 폐기물 관련 법령이 핵심이지만 현재 corpus에 없다.",
    ),
    (
        "lay-energy-0996",
        "해상풍력 공사·납품 분야는 발주·조달·산업정책 자료가 핵심이다.",
    ),
)

RISK_GROUPS = (
    (
        "질문이 넓거나 추가 사실이 필요한 후보",
        "broad_or_missing_facts",
        BROAD_OR_MISSING_FACTS,
    ),
    (
        "시점·실시간·개인 데이터가 필요한 후보",
        "time_or_live_data",
        TIME_OR_LIVE_DATA,
    ),
    (
        "현재 9종 corpus 밖 근거가 핵심일 가능성이 큰 후보",
        "outside_corpus",
        OUTSIDE_CORPUS,
    ),
)

REVIEW_DECISIONS = {
    "lay-energy-0001": "keep",
    "lay-energy-0002": "keep",
    "lay-energy-0084": "clarification_required",
    "lay-energy-0101": "clarification_required",
    "lay-energy-0111": "clarification_required",
    "lay-energy-0116": "clarification_required",
    "lay-energy-0171": "clarification_required",
    "lay-energy-0201": "clarification_required",
    "lay-energy-0251": "clarification_required",
    "lay-energy-0291": "unanswerable",
    "lay-energy-0351": "unanswerable",
    "lay-energy-0381": "unanswerable",
    "lay-energy-0441": "clarification_required",
    "lay-energy-0550": "unanswerable",
    "lay-energy-0605": "unanswerable",
    "lay-energy-0641": "unanswerable",
    "lay-energy-0646": "clarification_required",
    "lay-energy-0671": "unanswerable",
    "lay-energy-0726": "unanswerable",
    "lay-energy-0731": "unanswerable",
    "lay-energy-0741": "clarification_required",
    "lay-energy-0756": "unanswerable",
    "lay-energy-0766": "unanswerable",
    "lay-energy-0796": "unanswerable",
    "lay-energy-0800": "unanswerable",
    "lay-energy-0826": "unanswerable",
    "lay-energy-0836": "unanswerable",
    "lay-energy-0846": "clarification_required",
    "lay-energy-0881": "unanswerable",
    "lay-energy-0911": "unanswerable",
    "lay-energy-0921": "unanswerable",
    "lay-energy-0926": "unanswerable",
    "lay-energy-0956": "unanswerable",
    "lay-energy-0961": "clarification_required",
    "lay-energy-0996": "unanswerable",
}
REVIEW_DECISION_LABELS = {
    "keep": "유지",
    "clarification_required": "clarification_required 대조군",
    "unanswerable": "unanswerable 대조군",
}


class ApprovalReviewError(ValueError):
    """Raised when the fixed review cannot safely be rendered."""


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()


def _question_set_sha256(questions: Sequence[Mapping[str, object]]) -> str:
    return _canonical_sha256(
        [
            {
                "id": question.get("id"),
                "question": question.get("question"),
            }
            for question in questions
        ]
    )


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ApprovalReviewError(f"{label} must be an object")
    return value


def validated_questions(bank: Mapping[str, object]) -> list[Mapping[str, object]]:
    """Validate the exact fixed question bank used by this review."""

    expected_root = {
        "schema_version": 1,
        "bank_version": BANK_VERSION,
        "status": BANK_STATUS,
        "question_count": QUESTION_COUNT,
        "question_set_sha256": QUESTION_SET_SHA256,
        "question_scope_set_sha256": QUESTION_SCOPE_SET_SHA256,
    }
    for field, expected in expected_root.items():
        if bank.get(field) != expected:
            raise ApprovalReviewError(f"source bank {field} does not match the review contract")

    generation = _mapping(bank.get("generation_method"), label="generation_method")
    if generation.get("scenario_count") != SCENARIO_FAMILY_COUNT:
        raise ApprovalReviewError("source bank must declare exactly 200 scenario families")
    if generation.get("query_variants_per_scenario") != QUESTIONS_PER_FAMILY:
        raise ApprovalReviewError("source bank must declare exactly five variants per family")

    annotation = _mapping(bank.get("annotation_contract"), label="annotation_contract")
    expected_annotation = {
        "answers_included": False,
        "qrels_included": False,
        "expected_documents_included": False,
        "retrieval_experiment_executed": False,
    }
    for field, expected in expected_annotation.items():
        if annotation.get(field) is not expected:
            raise ApprovalReviewError(f"source bank unexpectedly declares {field}")

    corpus = _mapping(bank.get("corpus_context"), label="corpus_context")
    expected_temporal_context = {
        "corpus_snapshot_id": QUESTION_BANK_CONTEXT_CORPUS_SNAPSHOT_ID,
        "supported_as_of_from": QUESTION_BANK_CONTEXT_SUPPORTED_AS_OF_FROM.isoformat(),
        "supported_as_of_through": (QUESTION_BANK_CONTEXT_SUPPORTED_AS_OF_THROUGH.isoformat()),
    }
    for field, expected in expected_temporal_context.items():
        if corpus.get(field) != expected:
            raise ApprovalReviewError(f"source bank corpus {field} does not match the review")
    if corpus.get("catalog_title_set_sha256") != CATALOG_TITLE_SET_SHA256:
        raise ApprovalReviewError("source bank corpus title hash does not match the review")
    titles = corpus.get("catalog_titles")
    if not isinstance(titles, list) or tuple(titles) != CATALOG_TITLES:
        raise ApprovalReviewError("source bank corpus titles do not match the review")

    raw_questions = bank.get("questions")
    if not isinstance(raw_questions, list) or len(raw_questions) != QUESTION_COUNT:
        raise ApprovalReviewError("source bank must contain exactly 1000 questions")
    if any(not isinstance(question, Mapping) for question in raw_questions):
        raise ApprovalReviewError("every question must be an object")
    questions: list[Mapping[str, object]] = list(raw_questions)

    families: Counter[str] = Counter()
    family_intents: dict[str, set[str]] = {}
    family_technologies: dict[str, set[str]] = {}
    for index, question in enumerate(questions, start=1):
        expected_id = f"lay-energy-{index:04d}"
        question_id = question.get("id")
        text = question.get("question")
        if question_id != expected_id:
            raise ApprovalReviewError(f"question {index} must have ID {expected_id}")
        if not isinstance(text, str) or not text.strip():
            raise ApprovalReviewError(f"question {expected_id} has invalid text")
        if question.get("question_sha256") != _text_sha256(text):
            raise ApprovalReviewError(f"question {expected_id} text SHA-256 mismatch")
        if question.get("evaluation_annotation_status") != QUESTION_STATUS:
            raise ApprovalReviewError(f"question {expected_id} is not an unannotated draft")

        family = question.get("scenario_family_id")
        intent = question.get("intent")
        technology = question.get("technology")
        if not all(isinstance(value, str) and value for value in (family, intent, technology)):
            raise ApprovalReviewError(f"question {expected_id} has invalid scope fields")
        assert isinstance(family, str)
        assert isinstance(intent, str)
        assert isinstance(technology, str)
        families[family] += 1
        family_intents.setdefault(family, set()).add(intent)
        family_technologies.setdefault(family, set()).add(technology)

    if len(families) != SCENARIO_FAMILY_COUNT or set(families.values()) != {QUESTIONS_PER_FAMILY}:
        raise ApprovalReviewError("questions must form 200 families of five")
    if any(len(intents) != 1 for intents in family_intents.values()):
        raise ApprovalReviewError("a scenario family cannot mix intents")
    if any(len(technologies) != 1 for technologies in family_technologies.values()):
        raise ApprovalReviewError("a scenario family cannot mix technologies")

    if _question_set_sha256(questions) != QUESTION_SET_SHA256:
        raise ApprovalReviewError("calculated question set SHA-256 does not match")
    calculated_scope_sha256 = question_scope_set_sha256(questions)
    if calculated_scope_sha256 != QUESTION_SCOPE_SET_SHA256:
        raise ApprovalReviewError("calculated question scope set SHA-256 does not match")

    selected_ids = [*REPRESENTATIVE_IDS]
    for _title, _key, entries in RISK_GROUPS:
        selected_ids.extend(question_id for question_id, _reason in entries)
    known_ids = {str(question["id"]) for question in questions}
    missing_selected_ids = sorted(set(selected_ids) - known_ids)
    if missing_selected_ids:
        raise ApprovalReviewError(
            f"review selection refers to missing questions: {missing_selected_ids}"
        )
    risk_ids = [
        question_id for _title, _key, entries in RISK_GROUPS for question_id, _reason in entries
    ]
    if len(risk_ids) != 35 or len(set(risk_ids)) != 35:
        raise ApprovalReviewError("risk review must contain 35 unique question IDs")
    if len(REPRESENTATIVE_IDS) != 15 or len(set(REPRESENTATIVE_IDS)) != 15:
        raise ApprovalReviewError("representative review must contain 15 unique question IDs")
    if set(REVIEW_DECISIONS) != set(risk_ids):
        raise ApprovalReviewError("every risk-review question must have exactly one decision")
    if set(REVIEW_DECISIONS.values()) - set(REVIEW_DECISION_LABELS):
        raise ApprovalReviewError("risk-review decision contains an unsupported value")
    return questions


def load_question_bank(path: Path) -> Mapping[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ApprovalReviewError(f"could not read source bank: {path}") from error
    return _mapping(value, label="source bank")


def _cell(value: object) -> str:
    return " ".join(str(value).split()).replace("|", "\\|")


def _question_by_id(
    questions: Sequence[Mapping[str, object]],
) -> dict[str, Mapping[str, object]]:
    return {str(question["id"]): question for question in questions}


def _risk_table(
    entries: Sequence[tuple[str, str]],
    by_id: Mapping[str, Mapping[str, object]],
) -> list[str]:
    lines = [
        "| ID | 질문 | 검토가 필요한 이유 | 사용자 결정 |",
        "|---|---|---|---|",
    ]
    for question_id, reason in entries:
        question = by_id[question_id]
        decision = REVIEW_DECISION_LABELS[REVIEW_DECISIONS[question_id]]
        lines.append(
            f"| `{_cell(question_id)}` | {_cell(question['question'])} | "
            f"{_cell(reason)} | **{_cell(decision)}** |"
        )
    return lines


def render_approval_review(bank: Mapping[str, object]) -> str:
    """Return deterministic Markdown for the fixed question approval review."""

    questions = validated_questions(bank)
    by_id = _question_by_id(questions)
    intent_counts = Counter(str(question["intent"]) for question in questions)
    lines = [
        "# 실험 D 일반 사용자 질문 승인 검토표 v1",
        "",
        (
            "> 생성 명령: `uv run --directory apps/api python -m "
            "scripts.render_experiment_d_layperson_approval_review`"
        ),
        f"> 입력 bank: `{BANK_VERSION}` (`{BANK_STATUS}`)",
        f"> question set SHA-256: `{QUESTION_SET_SHA256}`",
        f"> question scope set SHA-256: `{QUESTION_SCOPE_SET_SHA256}`",
        (
            "> 범위: 질문 문구 승인 검토만 수행 — 정답·qrels·검색 후보·점수·검색 결과를 "
            "생성하지 않음"
        ),
        "",
        "[전체 1,000문항 읽기본](experiment-d-lay-energy-query-bank-v1.md)",
        "",
        "## 이 문서에서 결정할 것",
        "",
        "각 질문은 다음 중 하나로 검토한다.",
        "",
        "- **유지**: 현재 문구를 질문은행에 남긴다.",
        "- **수정**: 필요한 지역·용량·시점 등 사실을 넣거나 표현을 고친다.",
        "- **제외**: 실험 D 목적과 맞지 않아 질문은행에서 뺀다.",
        (
            "- **대조군으로 유지**: 추가 질문이 필요한 `clarification_required`, 일부만 "
            "답할 수 있는 `partially_answerable`, 현재 corpus로 답할 수 없는 `unanswerable` "
            "후보로 남긴다."
        ),
        "",
        (
            "여기서 고르는 대조군 유형은 질문 검토 의도일 뿐 최종 정답 라벨이 아니다. "
            "질문 승인 뒤 공식 원문을 검색 결과와 독립적으로 검토하여 answerability와 "
            "qrels를 별도 gold에 확정한다."
        ),
        "",
        (
            "이번 검토에서는 질문 문구가 넓거나 여러 요소를 요구한다는 이유만 있으면 유지했다. "
            "결론에 필요한 사용자 사실이 빠져 확정할 수 없으면 `clarification_required`, "
            "실시간·개인·시장·계약·사업 자료 또는 현재 corpus 밖 근거가 핵심이면 "
            "`unanswerable` 검토 의도로 분류했다. 단어 포함 여부가 아니라 검토 사유의 의미로 "
            "판정했다."
        ),
        "",
        "## 구조 확인",
        "",
        f"- 질문: {QUESTION_COUNT}개",
        f"- scenario family: {SCENARIO_FAMILY_COUNT}개 × {QUESTIONS_PER_FAMILY}문항",
        f"- intent: {len(intent_counts)}개",
        "- 모든 질문 상태: `not_annotated`",
        "- 현재 검토 corpus: 에너지 법령·기술기준 9종",
        (
            "- 현재 corpus 지원 기준일: "
            f"`{QUESTION_BANK_CONTEXT_SUPPORTED_AS_OF_FROM.isoformat()}` ~ "
            f"`{QUESTION_BANK_CONTEXT_SUPPORTED_AS_OF_THROUGH.isoformat()}` (양끝 포함)"
        ),
        "",
        "## Intent별 대표 질문 15개",
        "",
        "| Intent | ID | 질문 |",
        "|---|---|---|",
    ]
    for question_id in REPRESENTATIVE_IDS:
        question = by_id[question_id]
        lines.append(
            f"| {_cell(question['intent'])} | `{_cell(question_id)}` | "
            f"{_cell(question['question'])} |"
        )

    lines.extend(
        [
            "",
            "## 고위험 질문 35개",
            "",
            (
                "아래 결정은 질문을 삭제하지 않고 대조군으로 유지하기 위한 검토 의도이며 gold "
                "정답이 아니다. 최종 answerability는 독립 근거 검토에서 다시 확정한다."
            ),
            "",
            "- 유지: 2개",
            "- `clarification_required` 대조군: 12개",
            "- `unanswerable` 대조군: 21개",
        ]
    )
    for title, key, entries in RISK_GROUPS:
        lines.extend(
            [
                "",
                f"### {title} — {len(entries)}개 (`{key}`)",
                "",
                *_risk_table(entries, by_id),
            ]
        )

    lines.extend(
        [
            "",
            "## 승인 확인",
            "",
            "- [x] `lay-energy-0511` 문구를 사용자 지정 문구로 수정했다.",
            "- [x] 질문이 넓거나 여러 요소를 요구한다는 이유만 있는 문항은 유지했다.",
            "- [x] 사용자 사실이 부족한 문항은 `clarification_required` 검토 의도로 정했다.",
            "- [x] 실시간 데이터나 법 이외 자료가 핵심인 문항은 `unanswerable` 검토 의도로 정했다.",
            "- [x] 전체 1,000문항과 새 질문·범위 SHA-256을 승인 대상으로 확인했다.",
            "",
            "## 고정 식별자",
            "",
            f"- bank version: `{BANK_VERSION}`",
            f"- bank status: `{BANK_STATUS}`",
            f"- question count: `{QUESTION_COUNT}`",
            f"- question set SHA-256: `{QUESTION_SET_SHA256}`",
            f"- question scope set SHA-256: `{QUESTION_SCOPE_SET_SHA256}`",
            f"- [전체 1,000문항 읽기본]({FULL_REVIEW_LINK})",
        ]
    )
    return "\n".join(lines) + "\n"


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Render the fixed Experiment D layperson question approval review"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(argv)
    bank = load_question_bank(args.input)
    rendered = render_approval_review(bank)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(f"approval_review={args.output}")
    print(f"approval_review_sha256={hashlib.sha256(rendered.encode('utf-8')).hexdigest()}")
    print(f"question_count={QUESTION_COUNT}")
    print("answers_generated=false")
    print("qrels_generated=false")
    print("search_executed=false")
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised through public functions
    raise SystemExit(main())
