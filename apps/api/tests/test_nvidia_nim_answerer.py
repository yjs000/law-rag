from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.adapters.nvidia_nim_answerer import NvidiaNimAnswerer
from app.domain.catalog import SourceKind
from app.domain.schemas import QuestionRequest, SearchHit


def _answerer() -> NvidiaNimAnswerer:
    return NvidiaNimAnswerer(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/nemotron-3-ultra-550b-a55b",
        timeout_seconds=30,
        max_output_tokens=4096,
    )


def _hit() -> SearchHit:
    return SearchHit(
        provision_id=uuid4(),
        document_id=uuid4(),
        document_title="전기사업법",
        source_kind=SourceKind.LAW,
        version_label="MST 1",
        effective_from=date(2026, 1, 1),
        effective_to=None,
        path="제1조",
        content="전기사업에 관한 근거",
        source_url="https://www.law.go.kr/법령/전기사업법/제1조",
    )


@pytest.mark.asyncio
async def test_nvidia_nim_uses_guided_schema_and_validates_answer() -> None:
    answerer = _answerer()
    captured: dict[str, object] = {}
    payload = {
        "summary": "전기사업에 관한 근거입니다.",
        "scope": "기준일 현재 검색 범위",
        "sections": [
            {
                "claim": "전기사업에 관한 근거",
                "explanation": "원문 확인",
                "citation_ids": ["C1"],
            }
        ],
        "checklist": [
            {"label": "원문 확인", "status": "check", "citation_ids": ["C1"]}
        ],
        "limitations": [],
    }

    async def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))]
        )

    answerer.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    draft = await answerer.answer(QuestionRequest(question="전기사업 근거"), [_hit()])

    assert draft.sections[0].citation_ids == ["C1"]
    assert captured["model"] == "nvidia/nemotron-3-ultra-550b-a55b"
    assert captured["max_tokens"] == 4096
    assert captured["extra_body"]["chat_template_kwargs"] == {"enable_thinking": False}
    assert captured["extra_body"]["guided_json"]["type"] == "object"


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [None, "not-json", "{}"])
async def test_nvidia_nim_rejects_missing_or_invalid_structured_output(content) -> None:
    answerer = _answerer()

    async def create(**kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    answerer.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    expected = ValueError if content is None else ValidationError
    with pytest.raises(expected):
        await answerer.answer(QuestionRequest(question="전기사업 근거"), [_hit()])


def test_nvidia_nim_rejects_unapproved_base_url() -> None:
    with pytest.raises(ValueError, match="unsupported NVIDIA"):
        NvidiaNimAnswerer(
            api_key="test-key",
            base_url="https://attacker.example/v1",
            model="nvidia/nemotron-3-ultra-550b-a55b",
            timeout_seconds=30,
            max_output_tokens=4096,
        )
