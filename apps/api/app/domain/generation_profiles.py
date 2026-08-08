from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class GenerationProfile:
    """0025 M5 item 4: model/prompt/schema/context/sampling settings, versioned together.

    `sha256` lets a diagnostics record or E-run artifact cite exactly which combination
    produced an answer without re-serializing every field. Any field change is a new
    profile - bump `key`/`profile_version` rather than editing values in place once an
    E run has cited a profile's sha256.
    """

    key: str
    provider: Literal["openai", "nvidia_nim"]
    model: str
    prompt_version: str
    schema_version: str
    context_version: str
    temperature: float
    top_p: float
    max_output_tokens: int
    profile_version: str

    @property
    def sha256(self) -> str:
        payload = "|".join(f"{k}={v}" for k, v in sorted(asdict(self).items()))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# TODO(2026-08-08, 0025 M5): temperature=0.3은 잠정값이다. 기존 1.0은 근거 없는 하드코딩
# 이었다(git blame: 45edf43, 설명 없음). 법률 답변처럼 재현성이 중요한 출력에 맞춰
# 사용자 결정으로 0.3으로 낮췄지만, D-10/E-10 실제 실행으로 검증 전까지는 확정이 아니다.
# 검증 제안: nvidia_nim_answerer.py의 동일 TODO 참고 - D-10 10문항을 온도
# {0.0, 0.3, 0.7} 각 3회 반복 호출해 재현성(변동률)과 gold answerability 일치율을 같이
# 보고 E1(pilot 50문항) 전에 확정한다.
NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE = GenerationProfile(
    key="nvidia-nemotron-3-ultra-550b-a55b-answer-v1",
    provider="nvidia_nim",
    model="nvidia/nemotron-3-ultra-550b-a55b",
    prompt_version="answer-system-prompt-v1",  # openai_answerer.build_messages()
    schema_version="draft-answer-v1",  # openai_answerer.DraftAnswer
    context_version="m4-frozen-r1-a",  # 0025 M4 winner: R1+A
    temperature=0.3,
    top_p=0.95,
    max_output_tokens=4096,
    profile_version="1",
)

# MOCK/미확정, 2026-08-08: OpenAI 경로(openai_answerer.py)는 현재 temperature/top_p를
# API 호출에 명시하지 않아 provider 기본값에 의존한다 - NVIDIA 경로와 sampling 설정이
# 불일치한다. M5 item 3(provider를 nvidia_nim으로 고정)이 확정되면 이 프로필은 참고용으로만
# 남고 실질적으로 쓰이지 않을 가능성이 높아, 지금은 값을 추정하지 않고 None으로 비워둔다.
OPENAI_GPT_5_6_TERRA_ANSWER_PROFILE = GenerationProfile(
    key="openai-gpt-5-6-terra-answer-v1",
    provider="openai",
    model="gpt-5.6-terra",
    prompt_version="answer-system-prompt-v1",
    schema_version="draft-answer-v1",
    context_version="m4-frozen-r1-a",
    temperature=-1.0,  # sentinel: 실제로는 미지정(API 기본값) - MOCK, 확인 필요
    top_p=-1.0,  # sentinel: 실제로는 미지정(API 기본값) - MOCK, 확인 필요
    max_output_tokens=4096,
    profile_version="1",
)
