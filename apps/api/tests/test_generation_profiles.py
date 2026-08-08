from app.domain.generation_profiles import (
    NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE,
    GenerationProfile,
)


def test_sha256_is_stable_for_identical_profiles() -> None:
    duplicate = GenerationProfile(
        key=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.key,
        provider=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.provider,
        model=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.model,
        prompt_version=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.prompt_version,
        schema_version=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.schema_version,
        context_version=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.context_version,
        temperature=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.temperature,
        top_p=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.top_p,
        max_output_tokens=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.max_output_tokens,
        profile_version=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.profile_version,
    )
    assert duplicate.sha256 == NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.sha256


def test_sha256_changes_when_a_sampling_value_changes() -> None:
    changed = GenerationProfile(
        key=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.key,
        provider=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.provider,
        model=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.model,
        prompt_version=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.prompt_version,
        schema_version=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.schema_version,
        context_version=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.context_version,
        temperature=0.2,
        top_p=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.top_p,
        max_output_tokens=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.max_output_tokens,
        profile_version=NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.profile_version,
    )
    assert changed.sha256 != NVIDIA_NEMOTRON_ULTRA_ANSWER_PROFILE.sha256
