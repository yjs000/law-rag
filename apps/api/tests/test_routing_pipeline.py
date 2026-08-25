import json
from types import SimpleNamespace

import pytest

from app.adapters.nvidia_nim_route_classifier import NvidiaNimQuestionRouter
from app.domain.routing import QuestionRouter


def test_production_adapter_implements_single_question_router() -> None:
    assert issubclass(NvidiaNimQuestionRouter, QuestionRouter)


@pytest.mark.asyncio
async def test_nvidia_router_uses_one_question_prompt_without_embedding_hint() -> None:
    router = NvidiaNimQuestionRouter(
        api_key="test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="nvidia/test-router",
        timeout_seconds=10,
    )
    captured: dict[str, object] = {}

    async def create(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content=json.dumps(
                            {
                                "route": "legal_search",
                                "confidence": 0.8,
                                "reason": "법령으로 설명할 수 있습니다.",
                                "missing_fields": [],
                            }
                        )
                    )
                )
            ]
        )

    router.client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )

    judgment = await router.route("허가 절차를 알려주세요.")

    assert judgment.route == "legal_search"
    assert judgment.confidence == 0.8
    messages = captured["messages"]
    assert len(messages) == 2
    assert "허가 절차를 알려주세요." in messages[1]["content"]
    assert "유사" not in " ".join(message["content"] for message in messages)
    assert "hint" not in " ".join(message["content"] for message in messages).lower()
