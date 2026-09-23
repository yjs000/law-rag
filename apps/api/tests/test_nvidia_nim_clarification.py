import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.adapters.nvidia_nim_clarification import NvidiaNimClarificationInterpreter
from app.adapters.structured_clarification_continuation import (
    StructuredClarificationContinuationExtractor,
)
from app.bootstrap import (
    build_nvidia_clarification_interpreter,
    build_structured_clarification_continuation_extractor,
)
from app.settings import Settings


def _interpreter() -> NvidiaNimClarificationInterpreter:
    return NvidiaNimClarificationInterpreter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3-ultra-550b-a55b",
        timeout_seconds=8,
    )


def test_composition_factory_uses_the_configured_generation_model() -> None:
    interpreter = build_nvidia_clarification_interpreter(
        Settings(
            nvidia_api_key="test-key",
            nvidia_generation_model="nvidia/test-generation-model",
        )
    )

    assert interpreter.model == "nvidia/test-generation-model"


def test_composition_factory_uses_non_nvidia_continuation_extractor() -> None:
    assert isinstance(
        build_structured_clarification_continuation_extractor(),
        StructuredClarificationContinuationExtractor,
    )


def test_build_continuation_extraction_messages_includes_fact_ids_and_user_text() -> None:
    from app.adapters.nvidia_nim_clarification import build_continuation_extraction_messages
    from app.domain.clarification import RequiredFact, FactStatus

    facts = (
        RequiredFact(
            id="fact-1",
            label="설비 용량",
            why_needed="적용 요건을 가릅니다.",
            blocking=True,
            group="사업 정보",
            priority=1,
        ),
    )

    messages = build_continuation_extraction_messages(
        original_question="태양광 발전 사업의 허가 요건은 무엇인가요?",
        unresolved_facts=facts,
        user_text="100kW입니다.",
    )

    assert messages[0]["role"] == "system"
    assert "신뢰하지 않는" in messages[0]["content"]
    assert messages[1]["role"] == "user"
    assert "fact-1" in messages[1]["content"]
    assert "설비 용량" in messages[1]["content"]
    assert "100kW입니다." in messages[1]["content"]


def test_build_continuation_extraction_messages_handles_no_unresolved_facts() -> None:
    from app.adapters.nvidia_nim_clarification import build_continuation_extraction_messages

    messages = build_continuation_extraction_messages(
        original_question="질문", unresolved_facts=(), user_text="답변"
    )

    assert messages[1]["content"].endswith("답변")


@pytest.mark.asyncio
async def test_initial_judgment_uses_configured_ultra_and_structured_fact_candidates() -> None:
    interpreter = _interpreter()
    captured: dict[str, object] = {}

    async def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "intent": "provide_facts",
                                "submitted_facts": [],
                                "required_facts": [
                                    {
                                        "label": "설비 용량",
                                        "why_needed": "적용 요건을 가릅니다.",
                                        "blocking": True,
                                        "group": "사업 정보",
                                    }
                                ],
                            }
                        )
                    )
                )
            ]
        )

    interpreter.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    judgment = await interpreter.judge_initial("태양광 발전 사업의 허가 요건은 무엇인가요?")

    assert judgment.required_facts[0].label == "설비 용량"
    assert captured["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert captured["extra_body"]["guided_json"]["type"] == "object"


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [None, "not-json", "{}"])
async def test_nvidia_clarification_rejects_missing_or_invalid_json(content) -> None:
    interpreter = _interpreter()

    async def create(**kwargs):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])

    interpreter.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    expected = ValueError if content is None else ValidationError
    with pytest.raises(expected):
        await interpreter.judge_initial("허가 요건")


@pytest.mark.asyncio
async def test_nvidia_clarification_propagates_provider_failure_to_safe_workflow_boundary() -> None:
    interpreter = _interpreter()

    async def create(**kwargs):
        raise RuntimeError("provider details must stay private")

    interpreter.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    with pytest.raises(RuntimeError, match="provider details"):
        await interpreter.judge_initial("허가 요건")


@pytest.mark.asyncio
async def test_continuation_uses_structured_intent_and_fact_extraction_only() -> None:
    extractor = StructuredClarificationContinuationExtractor()
    judgment = await extractor.extract_continuation(
        original_question="태양광 발전 사업의 허가 요건은 무엇인가요?",
        unresolved_facts=(SimpleNamespace(id="fact-1", label="설비 용량"),),
        user_text=json.dumps(
            {
                "intent": "request_answer_now",
                "submitted_facts": [{"fact_id": "fact-1", "status": "answered", "value": "100kW"}],
            }
        ),
    )

    assert judgment.intent == "request_answer_now"
    assert judgment.submitted_facts[0].value == "100kW"
    assert judgment.required_facts == ()
    assert not hasattr(_interpreter(), "extract_continuation")
